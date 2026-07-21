from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

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


class AdjudicationRequest(BaseModel):
    winner_annotation_id: int
    comment: Optional[str] = None
    overrides: Dict[str, Any] = Field(default_factory=dict)
