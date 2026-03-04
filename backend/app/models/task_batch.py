import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    ANNOTATING = "annotating"
    SELF_REVIEW = "self_review"
    LEADER_REVIEW = "leader_review"
    EXPERT_REVIEW = "expert_review"
    LOCKED = "locked"


class TaskBatch(Base):
    __tablename__ = "task_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    action_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING
    )
    frame_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frame_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_frames: Mapped[int] = mapped_column(Integer, default=0)
    completed_frames: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="task_batches")
    assignee = relationship("User", back_populates="task_batches", foreign_keys=[assigned_to])
    review_records = relationship("ReviewRecord", back_populates="task_batch")
    annotations = relationship("FrameAnnotation", back_populates="task_batch", cascade="all, delete-orphan")
    batch_frames = relationship("BatchFrame", back_populates="task_batch", cascade="all, delete-orphan", order_by="BatchFrame.frame_index")
