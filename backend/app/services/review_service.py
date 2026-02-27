"""Three-level review state machine service.

State transitions:
  Pending -> Annotating -> SelfReview -> LeaderReview -> ExpertReview -> Locked
  With reject paths back to Annotating from any review stage.
"""

import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.task_batch import TaskBatch, TaskStatus
from app.models.review_record import ReviewRecord, ReviewLevel, ReviewResult
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

VALID_SUBMIT_TRANSITIONS = {
    TaskStatus.ANNOTATING: TaskStatus.SELF_REVIEW,
    TaskStatus.SELF_REVIEW: TaskStatus.LEADER_REVIEW,
}

REVIEW_LEVEL_FOR_STATUS = {
    TaskStatus.SELF_REVIEW: ReviewLevel.SELF,
    TaskStatus.LEADER_REVIEW: ReviewLevel.LEADER,
    TaskStatus.EXPERT_REVIEW: ReviewLevel.EXPERT,
}

PASS_TRANSITIONS = {
    TaskStatus.SELF_REVIEW: TaskStatus.LEADER_REVIEW,
    TaskStatus.LEADER_REVIEW: TaskStatus.EXPERT_REVIEW,
    TaskStatus.EXPERT_REVIEW: TaskStatus.LOCKED,
}


def submit_for_review(
    db: Session, batch: TaskBatch, user: User, comment: Optional[str] = None
) -> ReviewRecord:
    if batch.status == TaskStatus.ANNOTATING:
        if batch.assigned_to != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有任务负责人可以提交")
        batch.status = TaskStatus.SELF_REVIEW
    elif batch.status == TaskStatus.SELF_REVIEW:
        if batch.assigned_to != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "只有任务负责人可以提交自核")
        record = ReviewRecord(
            task_batch_id=batch.id,
            reviewer_id=user.id,
            review_level=ReviewLevel.SELF,
            result=ReviewResult.PASS,
            comment=comment,
        )
        db.add(record)
        batch.status = TaskStatus.LEADER_REVIEW
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"当前状态 {batch.status.value} 不允许提交审核",
        )

    db.commit()
    db.refresh(batch)
    return batch


def approve(
    db: Session, batch: TaskBatch, reviewer: User, comment: Optional[str] = None
) -> TaskBatch:
    review_level = REVIEW_LEVEL_FOR_STATUS.get(batch.status)
    if review_level is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"当前状态 {batch.status.value} 不在审核阶段",
        )

    _check_reviewer_permission(reviewer, review_level)

    record = ReviewRecord(
        task_batch_id=batch.id,
        reviewer_id=reviewer.id,
        review_level=review_level,
        result=ReviewResult.PASS,
        comment=comment,
    )
    db.add(record)

    new_status = PASS_TRANSITIONS[batch.status]
    batch.status = new_status
    db.commit()
    db.refresh(batch)
    return batch


def reject(
    db: Session, batch: TaskBatch, reviewer: User, comment: Optional[str] = None
) -> TaskBatch:
    review_level = REVIEW_LEVEL_FOR_STATUS.get(batch.status)
    if review_level is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"当前状态 {batch.status.value} 不在审核阶段",
        )

    _check_reviewer_permission(reviewer, review_level)

    record = ReviewRecord(
        task_batch_id=batch.id,
        reviewer_id=reviewer.id,
        review_level=review_level,
        result=ReviewResult.REJECT,
        comment=comment,
    )
    db.add(record)

    batch.status = TaskStatus.ANNOTATING
    db.commit()
    db.refresh(batch)
    return batch


def get_review_history(db: Session, task_batch_id: int) -> List[ReviewRecord]:
    return (
        db.query(ReviewRecord)
        .filter(ReviewRecord.task_batch_id == task_batch_id)
        .order_by(ReviewRecord.created_at.desc())
        .all()
    )


def _check_reviewer_permission(reviewer: User, level: ReviewLevel):
    if level == ReviewLevel.LEADER:
        if reviewer.role not in (UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "需要组长及以上权限")
    elif level == ReviewLevel.EXPERT:
        if reviewer.role not in (UserRole.ADMIN, UserRole.EXPERT):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "需要专家及以上权限")
