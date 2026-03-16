import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import PROJECT_ROOT, settings
from app.database import Base, SessionLocal, engine
from app.models import User, Project, TaskBatch, ReviewRecord, AuditLog, FrameAnnotation, BatchFrame
from app.core.security import hash_password

from app.api import auth, users, projects, tasks, annotations, review, progress, export


logger = logging.getLogger(__name__)
YOLO_POSE_MODEL_NAME = "yolov8n-pose.pt"
YOLO_POSE_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    _ensure_yolo_pose_model()
    Base.metadata.create_all(bind=engine)
    _ensure_task_batch_media_columns()
    _ensure_admin_user()
    _recover_interrupted_media_processes()
    yield


def _ensure_yolo_pose_model() -> None:
    model_dir = Path(settings.DATA_DIR) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    data_model = model_dir / YOLO_POSE_MODEL_NAME
    root_model = PROJECT_ROOT / YOLO_POSE_MODEL_NAME

    if data_model.exists() and data_model.stat().st_size > 0:
        logger.info("YOLO pose model ready: %s", data_model)
        return
    if root_model.exists() and root_model.stat().st_size > 0:
        logger.info("YOLO pose model found in project root: %s", root_model)
        return

    logger.info("YOLO pose model not found locally, downloading: %s", YOLO_POSE_MODEL_URL)
    try:
        with urlopen(YOLO_POSE_MODEL_URL, timeout=30) as response:
            data_model.write_bytes(response.read())
        if data_model.exists() and data_model.stat().st_size > 0:
            logger.info("YOLO pose model downloaded: %s", data_model)
        else:
            data_model.unlink(missing_ok=True)
            raise RuntimeError("YOLO pose model download finished but file is empty")
    except Exception as exc:
        logger.error("Failed to ensure YOLO pose model: %s", exc)
        raise RuntimeError("YOLO pose model is required at startup, but download failed") from exc


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
