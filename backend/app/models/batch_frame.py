"""任务批次下的帧媒体（图片或视频提取的帧）"""

from uuid import uuid4

from sqlalchemy import Boolean, Float, Integer, BigInteger, JSON, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BatchFrame(Base):
    """每个任务批次下的每一帧对应一个文件路径（图片或从视频提取的帧）"""
    __tablename__ = "batch_frames"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid4()))
    task_batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("task_batches.id"), nullable=False, index=True)
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)  # 相对 UPLOAD_DIR 的路径
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_rejected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selection_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selection_components: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    selection_strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    task_batch = relationship("TaskBatch", back_populates="batch_frames")
