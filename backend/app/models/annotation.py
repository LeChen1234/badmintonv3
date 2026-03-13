import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Enum, Text, Boolean, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnnotationStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class FrameAnnotation(Base):
    """每帧标注数据，包含标注人标识"""
    __tablename__ = "frame_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_batches.id"), nullable=False, index=True)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)

    annotator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    annotator_name: Mapped[str] = mapped_column(String(128), nullable=False)

    keypoints: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    action_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    action_phase: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quality_rating: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_ml_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[AnnotationStatus] = mapped_column(
        Enum(AnnotationStatus), nullable=False, default=AnnotationStatus.DRAFT
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    annotator = relationship("User", foreign_keys=[annotator_id])
    task_batch = relationship("TaskBatch", back_populates="annotations")
