import csv
import io
import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.models.annotation import FrameAnnotation, AnnotationStatus
from app.models.task_batch import TaskBatch
from app.schemas.export import ExportRequest, ExportOut
from app.core.security import get_current_user
from app.utils.audit import log_audit

router = APIRouter(prefix="/export", tags=["数据导出"])


def _gather_confirmed_annotations(db: Session, project_id: int):
    """收集某项目下所有已确认的标注数据"""
    batches = db.query(TaskBatch).filter(TaskBatch.project_id == project_id).all()
    batch_ids = [b.id for b in batches]
    if not batch_ids:
        return [], {}

    annotations = (
        db.query(FrameAnnotation)
        .filter(
            FrameAnnotation.task_batch_id.in_(batch_ids),
            FrameAnnotation.status == AnnotationStatus.CONFIRMED,
        )
        .order_by(FrameAnnotation.task_batch_id, FrameAnnotation.frame_index)
        .all()
    )

    batch_map = {b.id: b for b in batches}
    return annotations, batch_map


def _to_export_json(annotations, batch_map):
    """将确认的标注数据导出为 JSON（包含标注人信息）"""
    records = []
    for ann in annotations:
        batch = batch_map.get(ann.task_batch_id)
        records.append({
            "annotation_id": ann.id,
            "task_batch_id": ann.task_batch_id,
            "task_batch_name": batch.name if batch else "",
            "frame_index": ann.frame_index,
            "annotator_id": ann.annotator_id,
            "annotator_name": ann.annotator_name,
            "keypoints": ann.keypoints,
            "action_type": ann.action_type,
            "action_phase": ann.action_phase,
            "quality_rating": ann.quality_rating,
            "notes": ann.notes,
            "is_ml_generated": ann.is_ml_generated,
            "status": ann.status.value,
            "created_at": ann.created_at.isoformat() if ann.created_at else None,
            "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
        })
    return records


def _records_to_coco(records: list, project_name: str) -> dict:
    """将 records（_to_export_json 格式）转为 COCO 风格。"""
    kp_names = [
        "head_top", "head_center", "chin", "neck", "chest_center", "spine_mid", "pelvis_center",
        "left_shoulder", "left_elbow", "left_wrist", "left_palm",
        "right_shoulder", "right_elbow", "right_wrist", "right_palm",
        "left_hip", "left_knee", "left_ankle", "left_toe",
        "right_hip", "right_knee", "right_ankle", "right_toe",
        "racket_grip", "racket_head",
    ]
    categories = [{
        "id": 1,
        "name": "person",
        "supercategory": "person",
        "keypoints": kp_names,
        "skeleton": [
            [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6],
            [3, 7], [7, 8], [8, 9], [9, 10], [3, 11], [11, 12], [12, 13], [13, 14],
            [6, 15], [15, 16], [16, 17], [17, 18], [6, 19], [19, 20], [20, 21], [21, 22],
            [13, 23], [23, 24],
        ],
    }]
    images = []
    coco_annotations = []
    for idx, r in enumerate(records, start=1):
        images.append({
            "id": idx,
            "file_name": f"batch_{r['task_batch_id']}_frame_{r['frame_index']}.jpg",
            "width": 640,
            "height": 480,
        })
        keypoints = [0.0] * (25 * 3)
        img_w, img_h = 640, 480
        if isinstance(r.get("keypoints"), list):
            for kp in r["keypoints"]:
                name = kp.get("name") if isinstance(kp, dict) else None
                if name and name in kp_names:
                    i = kp_names.index(name)
                    x, y = float(kp.get("x", 0)), float(kp.get("y", 0))
                    if 0 <= x <= 100 and 0 <= y <= 100:
                        x, y = x / 100.0 * img_w, y / 100.0 * img_h
                    keypoints[i * 3] = round(x, 1)
                    keypoints[i * 3 + 1] = round(y, 1)
                    keypoints[i * 3 + 2] = 2 if (kp.get("visibility") or 0) > 0 else 0
        coco_annotations.append({
            "id": idx,
            "image_id": idx,
            "category_id": 1,
            "keypoints": keypoints,
            "num_keypoints": sum(1 for i in range(25) if keypoints[i * 3 + 2] > 0),
            "annotator_id": r.get("annotator_id"),
            "annotator_name": r.get("annotator_name"),
            "action_type": r.get("action_type"),
            "action_phase": r.get("action_phase"),
            "quality_rating": r.get("quality_rating"),
        })
    return {
        "info": {"description": project_name},
        "images": images,
        "annotations": coco_annotations,
        "categories": categories,
    }


def _records_to_csv(records: list) -> str:
    """将 records 转为 CSV 表格（含标注人）。"""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["task_batch_id", "frame_index", "annotator_id", "annotator_name", "action_type", "action_phase", "quality_rating", "notes"])
    for r in records:
        w.writerow([
            r.get("task_batch_id"),
            r.get("frame_index"),
            r.get("annotator_id"),
            r.get("annotator_name"),
            r.get("action_type") or "",
            r.get("action_phase") or "",
            r.get("quality_rating") or "",
            (r.get("notes") or "").replace("\n", " "),
        ])
    return out.getvalue()


@router.post("/{project_id}", response_model=ExportOut)
def export_project(
    project_id: int,
    req: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")

    annotations, batch_map = _gather_confirmed_annotations(db, project_id)
    records = _to_export_json(annotations, batch_map)

    fmt = (req.format or "json").lower()
    if fmt not in ("json", "coco", "csv"):
        fmt = "json"

    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "json" if fmt in ("json", "coco") else "csv"
    filename = f"project_{project_id}_confirmed_{timestamp}.{ext}"
    filepath = os.path.join(settings.EXPORT_DIR, filename)

    if fmt == "json":
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "project_id": project_id,
                "project_name": project.name,
                "export_time": datetime.now().isoformat(),
                "total_annotations": len(records),
                "annotations": records,
            }, f, ensure_ascii=False, indent=2)
    elif fmt == "coco":
        coco = _records_to_coco(records, project.name)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(coco, f, ensure_ascii=False, indent=2)
    else:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(_records_to_csv(records))

    log_audit(db, current_user.id, "export_project", f"project_id={project_id}, format={fmt}, count={len(records)}")

    return ExportOut(
        filename=filename,
        format=fmt,
        record_count=len(records),
        download_url=f"/api/export/{project_id}/download?filename={filename}",
    )


@router.get("/{project_id}/download")
def download_export(
    project_id: int,
    filename: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filepath = os.path.join(settings.EXPORT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "导出文件不存在")

    media_type = "text/csv" if filename.lower().endswith(".csv") else "application/json"
    return FileResponse(filepath, media_type=media_type, filename=filename)


@router.get("/{project_id}/confirmed-count")
def get_confirmed_count(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotations, _ = _gather_confirmed_annotations(db, project_id)
    return {"project_id": project_id, "confirmed_count": len(annotations)}
