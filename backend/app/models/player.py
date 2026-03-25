"""任务批次内的选手信息"""

from uuid import uuid4

from sqlalchemy import String, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Player(Base):
    """任务批次内的选手，支持多人标注同一视频时选择具体是谁"""
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4()))
    task_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_batches.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task_batch = relationship("TaskBatch", back_populates="players")
    annotations = relationship("FrameAnnotation", back_populates="selected_player_obj")
