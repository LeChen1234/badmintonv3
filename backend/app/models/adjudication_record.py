"""Expert decision turning blind duplicate annotations into one gold label."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AdjudicationRecord(Base):
    __tablename__ = "adjudication_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_batches.id"), nullable=False, index=True)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("players.id"), nullable=True)
    expert_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    winner_annotation_id: Mapped[int] = mapped_column(Integer, ForeignKey("frame_annotations.id"), nullable=False, index=True)
    candidate_annotation_ids: Mapped[Any] = mapped_column(JSON, nullable=False)
    disagreement_snapshot: Mapped[Any] = mapped_column(JSON, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    winner = relationship("FrameAnnotation", back_populates="adjudications_won", foreign_keys=[winner_annotation_id])
