import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Tuple
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.models.annotation import FrameAnnotation, AnnotationStatus
from app.models.task_batch import TaskBatch, TaskStatus
from app.models.batch_frame import BatchFrame
from app.schemas.export import ExportRequest, ExportOut
from app.core.security import get_current_user
from app.core.permissions import require_super_admin
from app.services.taxonomy_service import load_annotation_taxonomy
from app.services.research_release_service import build_release
from app.utils.audit import log_audit

router = APIRouter(prefix="/export", tags=["数据导出"])


def _gather_confirmed_annotations(db: Session, project_id: int, only_locked: bool = False):
    """收集某项目下所有已确认的标注数据"""
    batch_query = db.query(TaskBatch).filter(TaskBatch.project_id == project_id)
    if only_locked:
        batch_query = batch_query.filter(TaskBatch.status == TaskStatus.LOCKED)
    batches = batch_query.all()
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


def _build_frame_path_map(db: Session, batch_ids: list[int]) -> Dict[Tuple[int, int], str]:
    """构建 (task_batch_id, frame_index) 到相对文件路径的映射。"""
    if not batch_ids:
        return {}

    rows = (
        db.query(BatchFrame)
        .filter(BatchFrame.task_batch_id.in_(batch_ids))
        .all()
    )
    return {(row.task_batch_id, row.frame_index): row.file_path for row in rows}


def _load_image_size(rel_path: str, size_cache: Dict[str, Tuple[int, int]]) -> Tuple[int, int]:
    """从相对路径读取真实图片尺寸，失败时回退到默认值。"""
    default_size = (640, 480)
    if not rel_path:
        return default_size

    if rel_path in size_cache:
        return size_cache[rel_path]

    abs_path = rel_path
    if not os.path.isabs(abs_path):
        abs_path = os.path.join(settings.UPLOAD_DIR, rel_path)

    if not os.path.exists(abs_path):
        size_cache[rel_path] = default_size
        return default_size

    try:
        with Image.open(abs_path) as img:
            width, height = img.size
            if width > 0 and height > 0:
                size_cache[rel_path] = (int(width), int(height))
            else:
                size_cache[rel_path] = default_size
    except Exception:
        size_cache[rel_path] = default_size

    return size_cache[rel_path]


def _to_export_json(annotations, batch_map):
    """将确认的标注数据导出为 JSON（包含标注人信息）"""
    records = []
    for ann in annotations:
        batch = batch_map.get(ann.task_batch_id)
        player = ann.selected_player_obj
        batch_frame = next((frame for frame in (batch.batch_frames if batch else []) if frame.frame_index == ann.frame_index), None)
        records.append({
            "annotation_id": ann.id,
            "task_batch_id": ann.task_batch_id,
            "task_batch_name": batch.name if batch else "",
            "task_batch_uuid": batch.uuid if batch else None,
            "action_category": batch.action_category if batch else None,
            "match_uuid": batch.match_uuid if batch else None,
            "match_name": batch.match_name if batch else None,
            "match_format": batch.match_format if batch else None,
            "match_date": batch.match_date.isoformat() if batch and batch.match_date else None,
            "selection_metadata": batch.selection_metadata if batch else None,
            "video_id": batch.video_id if batch else None,
            "video_sha256": batch.video_sha256 if batch else None,
            "frame_index": ann.frame_index,
            "frame_timestamp_ms": batch_frame.timestamp_ms if batch_frame else 0,
            "frame_timestamp_seconds": round((batch_frame.timestamp_ms if batch_frame else 0) / 1000, 3),
            "annotator_id": ann.annotator_id,
            "annotator_name": ann.annotator_name,
            "selected_player_id": ann.selected_player_id,
            "selected_player_name": ann.selected_player_obj.name if ann.selected_player_obj else "",
            "selected_player_uuid": player.uuid if player else None,
            "subject_code": player.subject_code if player else None,
            "selected_player_profile": ({
                "gender": player.gender,
                "age": player.age,
                "height_cm": player.height_cm,
            } if player else None),
            "keypoints": ann.keypoints,
            "bbox": [ann.box_x, ann.box_y, ann.box_w, ann.box_h],
            "action_type": ann.action_type,
            "action_phase": ann.action_phase,
            "quality_rating": ann.quality_rating,
            "is_forced_action": ann.is_forced_action,
            "notes": ann.notes,
            "is_contact_event": bool(ann.is_contact_event),
            "contact": ann.contact,
            "is_ml_generated": ann.is_ml_generated,
            "taxonomy_version": ann.taxonomy_version,
            "assist_metadata": ann.assist_metadata,
            "assist_accepted": ann.assist_accepted,
            "annotation_duration_ms": ann.annotation_duration_ms,
            "revision_count": len(ann.revisions),
            "revision_summary": [
                {
                    "source": revision.source,
                    "changed_fields": revision.changed_fields,
                    "created_at": revision.created_at.isoformat() if revision.created_at else None,
                }
                for revision in ann.revisions
            ],
            "expert_adjudicated": bool(ann.adjudications_won),
            "status": ann.status.value,
            "created_at": ann.created_at.isoformat() if ann.created_at else None,
            "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
        })
    return records


def _records_to_coco(records: list, project_name: str, frame_path_map: Dict[Tuple[int, int], str] | None = None) -> dict:
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
            [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 7],
            [4, 8], [8, 9], [9, 10], [10, 11], [4, 12], [12, 13], [13, 14], [14, 15],
            [7, 16], [16, 17], [17, 18], [18, 19], [7, 20], [20, 21], [21, 22], [22, 23],
            [14, 24], [24, 25],
        ],
    }]
    images = []
    coco_annotations = []
    size_cache: Dict[str, Tuple[int, int]] = {}
    frame_path_map = frame_path_map or {}
    for idx, r in enumerate(records, start=1):
        rel_path = frame_path_map.get((r["task_batch_id"], r["frame_index"]), "")
        img_w, img_h = _load_image_size(rel_path, size_cache)
        images.append({
            "id": idx,
            "file_name": rel_path or f"batch_{r['task_batch_id']}_frame_{r['frame_index']}.jpg",
            "width": img_w,
            "height": img_h,
            "video_id": r.get("video_id"),
            "timestamp_ms": r.get("frame_timestamp_ms", 0),
            "license": 0,
            "flickr_url": "",
            "coco_url": "",
            "date_captured": "",
        })
        keypoints = [0.0] * (25 * 3)
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
        bbox = r.get("bbox") if isinstance(r.get("bbox"), list) else None
        area = 0
        if bbox and len(bbox) >= 4 and bbox[2] is not None and bbox[3] is not None:
            area = bbox[2] * bbox[3]

        coco_annotations.append({
            "id": idx,
            "image_id": idx,
            "category_id": 1,
            "segmentation": [],
            "keypoints": keypoints,
            "num_keypoints": sum(1 for i in range(25) if keypoints[i * 3 + 2] > 0),
            "annotator_id": r.get("annotator_id"),
            "annotator_name": r.get("annotator_name"),
            "selected_player_id": r.get("selected_player_id"),
            "selected_player_name": r.get("selected_player_name"),
            # Export record assembled from validated annotation fields.
            "bbox": r.get("bbox"),
            "area": area,
            "iscrowd": 0,
            "action_type": r.get("action_type"),
            "action_phase": r.get("action_phase"),
            "quality_rating": r.get("quality_rating"),
            "is_forced_action": bool(r.get("is_forced_action")),
            "is_contact_event": bool(r.get("is_contact_event")),
            "contact": r.get("contact"),
        })
    return {
        "info": {
            "year": datetime.now().year,
            "version": "1.1",
            "description": project_name,
            "contributor": "",
            "url": "",
            "date_created": datetime.now().isoformat(),
            "contact_centric": True,
        },
        "images": images,
        "annotations": coco_annotations,
        "categories": categories,
        "licenses": [],
    }


def _records_to_csv(records: list) -> str:
    """将 records 转为 CSV 表格（含标注人）。"""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "task_batch_id", "video_id", "frame_index", "frame_timestamp_ms", "frame_timestamp_seconds",
        "annotator_id", "annotator_name",
        "selected_player_id", "selected_player_name", "bbox",
        "action_type", "action_phase", "quality_rating", "is_forced_action",
        "is_contact_event", "contact_zone", "contact_u", "contact_v",
        "face_attitude", "support_foot", "notes",
    ])
    for r in records:
        bbox = r.get("bbox")
        bbox_value = json.dumps(bbox, ensure_ascii=False) if isinstance(bbox, list) else ""
        contact = r.get("contact") if isinstance(r.get("contact"), dict) else {}
        uv = contact.get("contact_uv") if isinstance(contact.get("contact_uv"), dict) else {}
        w.writerow([
            r.get("task_batch_id"),
            r.get("video_id") or "",
            r.get("frame_index"),
            r.get("frame_timestamp_ms", 0),
            r.get("frame_timestamp_seconds", 0),
            r.get("annotator_id"),
            r.get("annotator_name"),
            r.get("selected_player_id") or "",
            r.get("selected_player_name") or "",
            bbox_value,
            r.get("action_type") or "",
            r.get("action_phase") or "",
            r.get("quality_rating") or "",
            "1" if r.get("is_forced_action") else "0",
            "1" if r.get("is_contact_event") else "0",
            contact.get("contact_zone") or "",
            uv.get("u") if uv.get("u") is not None else "",
            uv.get("v") if uv.get("v") is not None else "",
            contact.get("face_attitude") or "",
            contact.get("support_foot") or "",
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
    require_super_admin(current_user)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")

    annotations, batch_map = _gather_confirmed_annotations(db, project_id, req.only_locked)
    records = _to_export_json(annotations, batch_map)
    records, release_manifest = build_release(records, project.uuid, only_locked_batches=req.only_locked)
    frame_path_map = _build_frame_path_map(db, list(batch_map.keys()))

    fmt = (req.format or "json").lower()
    if fmt not in ("json", "coco", "csv"):
        fmt = "json"

    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "json" if fmt in ("json", "coco") else "csv"
    filename = f"project_{project_id}_confirmed_{timestamp}.{ext}"
    filepath = os.path.join(settings.EXPORT_DIR, filename)

    if fmt == "json":
        taxonomy = load_annotation_taxonomy()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": "2.0",
                "project_id": project_id,
                "project_uuid": project.uuid,
                "project_name": project.name,
                "taxonomy_version": taxonomy.get("version"),
                "export_time": datetime.now().isoformat(),
                "selection": {"status": "confirmed", "only_locked_batches": req.only_locked},
                "group_split_key": "subject-match connected component",
                "release_manifest": release_manifest,
                "total_annotations": len(records),
                "annotations": records,
            }, f, ensure_ascii=False, indent=2)
    elif fmt == "coco":
        coco = _records_to_coco(records, project.name, frame_path_map)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(coco, f, ensure_ascii=False, indent=2)
    else:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(_records_to_csv(records))

    log_audit(db, current_user.id, "export_project", f"project_id={project_id}, format={fmt}, only_locked={req.only_locked}, count={len(records)}")

    return ExportOut(
        filename=filename,
        format=fmt,
        record_count=len(records),
        download_url=f"/api/export/{project_id}/download?filename={filename}",
        dataset_id=release_manifest["dataset_id"],
        dataset_sha256=release_manifest["sha256"],
        split_record_counts=release_manifest["split_record_counts"],
        warnings=release_manifest["warnings"],
        release_ready=release_manifest["release_ready"],
        quality_gates=release_manifest["quality_gates"],
    )


@router.get("/{project_id}/download")
def download_export(
    project_id: int,
    filename: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    export_root = Path(settings.EXPORT_DIR).resolve()
    filepath = (export_root / filename).resolve()
    expected_prefix = f"project_{project_id}_confirmed_"
    if filepath.parent != export_root or not filepath.name.startswith(expected_prefix):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法导出文件名")
    if not filepath.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "导出文件不存在")

    media_type = "text/csv" if filename.lower().endswith(".csv") else "application/json"
    return FileResponse(str(filepath), media_type=media_type, filename=filepath.name)


@router.get("/{project_id}/confirmed-count")
def get_confirmed_count(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    annotations, _ = _gather_confirmed_annotations(db, project_id)
    locked_annotations, _ = _gather_confirmed_annotations(db, project_id, only_locked=True)
    return {
        "project_id": project_id,
        "confirmed_count": len(annotations),
        "locked_confirmed_count": len(locked_annotations),
    }
