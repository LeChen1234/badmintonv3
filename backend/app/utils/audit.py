"""审计日志：记录关键操作。"""

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit(db: Session, user_id: int, action: str, detail: str | None = None) -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))
    db.commit()
