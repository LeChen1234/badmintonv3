"""Persistent evidence for one closed-loop annotation/training round."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActiveLearningRound(Base):
    __tablename__ = "active_learning_rounds"
    __table_args__ = (UniqueConstraint("project_id", "round_index", name="ux_active_round_project_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    round_index: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    selection_strategy: Mapped[str] = mapped_column(String(64), nullable=False, default="information_functional")
    annotation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    annotation_hours: Mapped[float] = mapped_column(Float, nullable=False)
    metrics: Mapped[Any] = mapped_column(JSON, nullable=False)
    component_gains: Mapped[Any] = mapped_column(JSON, nullable=False)
    marginal_utility: Mapped[Any] = mapped_column(JSON, nullable=False)
    recommended_weights: Mapped[Any] = mapped_column(JSON, nullable=False)
    stop_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
