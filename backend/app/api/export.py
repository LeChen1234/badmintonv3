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

    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"project_{project_id}_confirmed_{timestamp}.json"
    filepath = os.path.join(settings.EXPORT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "project_id": project_id,
            "project_name": project.name,
            "export_time": datetime.now().isoformat(),
            "total_annotations": len(records),
            "annotations": records,
        }, f, ensure_ascii=False, indent=2)

    return ExportOut(
        filename=filename,
        format="json",
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

    return FileResponse(
        filepath,
        media_type="application/json",
        filename=filename,
    )


@router.get("/{project_id}/confirmed-count")
def get_confirmed_count(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotations, _ = _gather_confirmed_annotations(db, project_id)
    return {"project_id": project_id, "confirmed_count": len(annotations)}
