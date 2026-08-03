"""Continuous action/phase annotations spanning a range of extracted frames."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.annotation import AnnotationStatus


class TemporalSegment(Base):
    __tablename__ = "temporal_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4())
    )
    task_batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("task_batches.id"), nullable=False, index=True
    )
    selected_player_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("players.id"), nullable=False, index=True
    )
    annotator_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    annotator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    end_frame: Mapped[int] = mapped_column(Integer, nullable=False)
    start_timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action_phase: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    execution: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    outcome: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[AnnotationStatus] = mapped_column(
        String(32), nullable=False, default=AnnotationStatus.DRAFT.value
    )
    confirmed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    task_batch = relationship("TaskBatch", back_populates="temporal_segments")
    selected_player = relationship("Player", foreign_keys=[selected_player_id])
    annotator = relationship("User", foreign_keys=[annotator_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])
