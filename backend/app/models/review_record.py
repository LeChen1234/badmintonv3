import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewLevel(str, enum.Enum):
    SELF = "self"
    LEADER = "leader"
    EXPERT = "expert"


class ReviewResult(str, enum.Enum):
    PASS = "pass"
    REJECT = "reject"


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_batches.id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    review_level: Mapped[ReviewLevel] = mapped_column(Enum(ReviewLevel), nullable=False)
    result: Mapped[ReviewResult] = mapped_column(Enum(ReviewResult), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    task_batch = relationship("TaskBatch", back_populates="review_records")
    reviewer = relationship("User", back_populates="review_records")
