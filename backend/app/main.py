import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.core.security import hash_password
from app.services.backup_service import BackupScheduler, create_backup_snapshot

from app.api import auth, users, projects, tasks, annotations, review, progress, export


logger = logging.getLogger(__name__)
YOLO_POSE_MODEL_NAME = "yolov8n-pose.pt"
YOLO_POSE_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-pose.pt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)
    _ensure_yolo_pose_model()
    Base.metadata.create_all(bind=engine)
    _ensure_super_admin_user()
    _recover_interrupted_media_processes()
    backup_scheduler = _setup_auto_backup()
    try:
        yield
    finally:
        if backup_scheduler:
            backup_scheduler.stop()


def _ensure_yolo_pose_model() -> None:
    model_dir = Path(settings.DATA_DIR) / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    data_model = model_dir / YOLO_POSE_MODEL_NAME

    if data_model.exists() and data_model.stat().st_size > 0:
        logger.info("YOLO pose model ready: %s", data_model)
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



def _recover_interrupted_media_processes():
    from app.services import task_service

    db = SessionLocal()
    try:
        task_service.recover_interrupted_media_processes(db)
    finally:
        db.close()


def _ensure_super_admin_user():
    from app.database import SessionLocal
    from app.models.user import UserRole

    db = SessionLocal()
    try:
        super_admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if super_admin:
            return

        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role=UserRole.SUPER_ADMIN,
                display_name="系统管理员",
                is_super_admin=True,
            )
            db.add(admin)
            logger.warning("No admin found, created default super admin account: admin/admin123")
        else:
            admin.role = UserRole.SUPER_ADMIN
            admin.is_super_admin = True
            logger.warning("No super admin found, promoted user '%s' to super admin", admin.username)
        db.commit()
    finally:
        db.close()


def _setup_auto_backup() -> BackupScheduler | None:
    if not settings.ENABLE_AUTO_BACKUP:
        logger.info("Automatic backup is disabled")
        return None

    try:
        initial_backup = create_backup_snapshot(
            sqlite_db_path=settings.SQLITE_DB_PATH,
            backup_dir=settings.BACKUP_DIR,
            keep_count=settings.BACKUP_KEEP_COUNT,
        )
        logger.info("Initial backup created: %s", initial_backup)
    except Exception as exc:
        logger.exception("Initial backup failed: %s", exc)

    scheduler = BackupScheduler(
        sqlite_db_path=settings.SQLITE_DB_PATH,
        backup_dir=settings.BACKUP_DIR,
        interval_minutes=settings.BACKUP_INTERVAL_MINUTES,
        keep_count=settings.BACKUP_KEEP_COUNT,
    )
    scheduler.start()
    return scheduler


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
