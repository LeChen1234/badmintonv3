"""Task batch management service."""

import logging
import shutil
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.task_batch import TaskBatch, TaskStatus
from app.models.user import User
from app.models.annotation import FrameAnnotation, AnnotationStatus
from app.models.review_record import ReviewRecord
from app.config import settings
from app.schemas.task_batch import TaskBatchCreate, TaskBatchUpdate

logger = logging.getLogger(__name__)


def create_task_batch(db: Session, data: TaskBatchCreate, creator: User) -> TaskBatch:
    batch = TaskBatch(
        project_id=data.project_id,
        name=data.name,
        action_category=data.action_category,
        assigned_to=data.assigned_to,
        frame_start=data.frame_start,
        frame_end=data.frame_end,
        total_frames=data.total_frames,
        deadline=data.deadline,
        status=TaskStatus.ANNOTATING if data.assigned_to else TaskStatus.PENDING,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_task_batch(db: Session, batch_id: int) -> Optional[TaskBatch]:
    return db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()


def list_task_batches(
    db: Session,
    project_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    status: Optional[TaskStatus] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[TaskBatch]:
    q = db.query(TaskBatch)
    if project_id is not None:
        q = q.filter(TaskBatch.project_id == project_id)
    if assigned_to is not None:
        q = q.filter(TaskBatch.assigned_to == assigned_to)
    if status is not None:
        q = q.filter(TaskBatch.status == status)
    return q.order_by(TaskBatch.created_at.desc()).offset(skip).limit(limit).all()


def update_task_batch(
    db: Session, batch: TaskBatch, data: TaskBatchUpdate
) -> TaskBatch:
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(batch, key, value)
    db.commit()
    db.refresh(batch)
    return batch


def assign_task(db: Session, batch: TaskBatch, user_id: int) -> TaskBatch:
    batch.assigned_to = user_id
    if batch.status == TaskStatus.PENDING:
        batch.status = TaskStatus.ANNOTATING
    db.commit()
    db.refresh(batch)
    return batch


def transition_status(db: Session, batch: TaskBatch, new_status: TaskStatus) -> TaskBatch:
    batch.status = new_status
    db.commit()
    db.refresh(batch)
    return batch


def sync_batch_completed_frames(db: Session, batch_id: int) -> int:
    """根据已确认标注数更新任务批次的 completed_frames，返回更新后的数量。"""
    from sqlalchemy import func
    count = db.query(func.count(FrameAnnotation.id)).filter(
        FrameAnnotation.task_batch_id == batch_id,
        FrameAnnotation.status == AnnotationStatus.CONFIRMED,
    ).scalar() or 0
    batch = db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()
    if batch:
        batch.completed_frames = count
        db.commit()
        db.refresh(batch)
    return count


def delete_task_batch(db: Session, batch: TaskBatch) -> None:
    """删除任务批次及其上传目录。"""
    upload_dir = Path(settings.UPLOAD_DIR) / f"batch_{batch.id}"

    db.query(ReviewRecord).filter(ReviewRecord.task_batch_id == batch.id).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()

    # 数据库提交成功后再清理磁盘，减少数据不一致风险。
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)
