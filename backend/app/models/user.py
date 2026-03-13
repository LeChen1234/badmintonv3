import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EXPERT = "expert"
    LEADER = "leader"
    STUDENT = "student"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    ls_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    task_batches = relationship("TaskBatch", back_populates="assignee", foreign_keys="TaskBatch.assigned_to")
    review_records = relationship("ReviewRecord", back_populates="reviewer")
    audit_logs = relationship("AuditLog", back_populates="user")
