from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.review_record import ReviewLevel, ReviewResult


class ReviewSubmit(BaseModel):
    """Student submits task for review."""
    comment: Optional[str] = None


class ReviewAction(BaseModel):
    """Leader/Expert approves or rejects."""
    result: ReviewResult
    comment: Optional[str] = None


class ReviewRecordOut(BaseModel):
    id: int
    task_batch_id: int
    reviewer_id: int
    reviewer_name: Optional[str] = None
    review_level: ReviewLevel
    result: ReviewResult
    comment: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
