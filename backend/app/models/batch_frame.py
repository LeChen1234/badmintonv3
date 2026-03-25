"""任务批次下的帧媒体（图片或视频提取的帧）"""

from uuid import uuid4

from sqlalchemy import Integer, String, ForeignKey
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

    task_batch = relationship("TaskBatch", back_populates="batch_frames")
