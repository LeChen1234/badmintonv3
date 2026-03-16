import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User, Project, TaskBatch, ReviewRecord, AuditLog, FrameAnnotation, BatchFrame
from app.core.security import hash_password

from app.api import auth, users, projects, tasks, annotations, review, progress, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_task_batch_media_columns()
    _ensure_admin_user()
    _recover_interrupted_media_processes()
    yield


def _ensure_task_batch_media_columns():
    inspector = inspect(engine)
    if "task_batches" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("task_batches")}
    statements = []
    if "media_process_status" not in existing_columns:
        statements.append("ALTER TABLE task_batches ADD COLUMN media_process_status VARCHAR(32) NOT NULL DEFAULT 'idle'")
    if "media_process_message" not in existing_columns:
        statements.append("ALTER TABLE task_batches ADD COLUMN media_process_message VARCHAR(512)")
    if "media_process_started_at" not in existing_columns:
        statements.append("ALTER TABLE task_batches ADD COLUMN media_process_started_at DATETIME")
    if "media_process_finished_at" not in existing_columns:
        statements.append("ALTER TABLE task_batches ADD COLUMN media_process_finished_at DATETIME")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _recover_interrupted_media_processes():
    from app.services import task_service

    db = SessionLocal()
    try:
        task_service.recover_interrupted_media_processes(db)
    finally:
        db.close()


def _ensure_admin_user():
    from app.database import SessionLocal
    from app.models.user import UserRole

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN,
                display_name="系统管理员",
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


app = FastAPI(
    title="羽毛球训练动作标注管理系统",
    description="Badminton Training Action Annotation Management Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(progress.router, prefix="/api")
app.include_router(export.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "badminton-management-backend",
        "ml_backend_enabled": settings.ENABLE_ML_BACKEND,
    }


@app.get("/api/config")
def get_config():
    """公开配置，供前端决定是否显示注册入口、ML 初标等。"""
    return {
        "allow_public_register": settings.ALLOW_PUBLIC_REGISTER,
        "ml_backend_enabled": settings.ENABLE_ML_BACKEND,
    }
