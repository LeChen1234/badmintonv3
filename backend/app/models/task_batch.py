import enum
from datetime import datetime, date
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, Enum, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    ANNOTATING = "annotating"
    SELF_REVIEW = "self_review"
    LEADER_REVIEW = "leader_review"
    EXPERT_REVIEW = "expert_review"
    LOCKED = "locked"


class MediaProcessStatus(str, enum.Enum):
    IDLE = "idle"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskBatch(Base):
    __tablename__ = "task_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4()))
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    action_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    assigned_to: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING
    )
    frame_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    frame_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_frames: Mapped[int] = mapped_column(Integer, default=0)
    completed_frames: Mapped[int] = mapped_column(Integer, default=0)
    media_process_status: Mapped[str] = mapped_column(String(32), nullable=False, default=MediaProcessStatus.IDLE.value)
    media_process_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    media_process_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    media_process_finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    match_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    match_uuid: Mapped[Optional[str]] = mapped_column(String(36), unique=True, index=True, nullable=True)
    match_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    metadata_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="task_batches")
    assignee = relationship("User", back_populates="task_batches", foreign_keys=[assigned_to])
    review_records = relationship("ReviewRecord", back_populates="task_batch", cascade="all, delete-orphan")
    annotations = relationship("FrameAnnotation", back_populates="task_batch", cascade="all, delete-orphan")
    batch_frames = relationship("BatchFrame", back_populates="task_batch", cascade="all, delete-orphan", order_by="BatchFrame.frame_index")
    players = relationship("Player", back_populates="task_batch", cascade="all, delete-orphan")
