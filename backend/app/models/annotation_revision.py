"""Append-only annotation revision event for pre-annotation correction analysis."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnnotationRevision(Base):
    __tablename__ = "annotation_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    annotation_id: Mapped[int] = mapped_column(Integer, ForeignKey("frame_annotations.id", ondelete="CASCADE"), nullable=False, index=True)
    editor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_edit")
    changed_fields: Mapped[Any] = mapped_column(JSON, nullable=False)
    before_snapshot: Mapped[Any] = mapped_column(JSON, nullable=False)
    after_snapshot: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    annotation = relationship("FrameAnnotation", back_populates="revisions")
    editor = relationship("User", foreign_keys=[editor_id])
