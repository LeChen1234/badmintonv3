from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.task_batch import TaskBatch
from app.schemas.review import ReviewSubmit, ReviewAction, ReviewRecordOut
from app.core.security import get_current_user
from app.services import review_service
from app.utils.audit import log_audit

router = APIRouter(prefix="/review", tags=["审核流程"])


@router.post("/{task_id}/submit")
def submit_review(
    task_id: int,
    data: ReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    batch = review_service.submit_for_review(db, batch, current_user, data.comment)
    log_audit(db, current_user.id, "submit_review", f"task_id={task_id}, status={batch.status.value}")
    return {"status": batch.status.value, "message": "提交成功"}


@router.post("/{task_id}/approve")
def approve_review(
    task_id: int,
    data: ReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    batch = review_service.approve(db, batch, current_user, data.comment)
    log_audit(db, current_user.id, "approve_review", f"task_id={task_id}")
    return {"status": batch.status.value, "message": "审核通过"}


@router.post("/{task_id}/reject")
def reject_review(
    task_id: int,
    data: ReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    batch = review_service.reject(db, batch, current_user, data.comment)
    log_audit(db, current_user.id, "reject_review", f"task_id={task_id}, comment={data.comment or ''}")
    return {"status": batch.status.value, "message": "已打回"}


@router.get("/{task_id}/history", response_model=List[ReviewRecordOut])
def review_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = review_service.get_review_history(db, task_id)
    result = []
    for r in records:
        result.append(ReviewRecordOut(
            id=r.id,
            task_batch_id=r.task_batch_id,
            reviewer_id=r.reviewer_id,
            reviewer_name=r.reviewer.display_name if r.reviewer else None,
            review_level=r.review_level,
            result=r.result,
            comment=r.comment,
            created_at=r.created_at,
        ))
    return result
