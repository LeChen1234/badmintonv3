import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.request import urlopen
from sqlalchemy import text

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.core.security import hash_password
from app.services.backup_service import BackupScheduler, create_backup_snapshot
from app.services.taxonomy_service import load_annotation_taxonomy

from app.api import auth, users, projects, tasks, annotations, review, progress, export, research


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
    load_annotation_taxonomy()
    Base.metadata.create_all(bind=engine)
    _ensure_contact_annotation_columns()
    _ensure_super_admin_user()
    _recover_interrupted_media_processes()
    backup_scheduler = _setup_auto_backup()
    try:
        yield
    finally:
        if backup_scheduler:
            backup_scheduler.stop()


def _ensure_contact_annotation_columns() -> None:
    """Add backward-compatible annotation columns for legacy local SQLite DBs."""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(frame_annotations)").fetchall()
        existing = {r[1] for r in rows}  # name column
        if "is_contact_event" not in existing:
            conn.exec_driver_sql(
                "ALTER TABLE frame_annotations ADD COLUMN is_contact_event BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("Added column frame_annotations.is_contact_event")
        if "contact" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN contact JSON")
            logger.info("Added column frame_annotations.contact")
        if "taxonomy_version" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN taxonomy_version VARCHAR(32)")
        if "assist_metadata" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN assist_metadata JSON")
        if "assist_accepted" not in existing:
            conn.exec_driver_sql(
                "ALTER TABLE frame_annotations ADD COLUMN assist_accepted BOOLEAN NOT NULL DEFAULT 0"
            )
        if "annotation_duration_ms" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN annotation_duration_ms INTEGER")
        if "workflow_stage" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN workflow_stage VARCHAR(32) NOT NULL DEFAULT 'student_coarse'")
        if "expert_review_required" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN expert_review_required BOOLEAN NOT NULL DEFAULT 0")
        if "expert_review_reasons" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN expert_review_reasons JSON")
        if "expert_reviewed_by" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN expert_reviewed_by INTEGER REFERENCES users(id)")
        if "expert_reviewed_at" not in existing:
            conn.exec_driver_sql("ALTER TABLE frame_annotations ADD COLUMN expert_reviewed_at DATETIME")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_annotations_expert_queue "
            "ON frame_annotations (expert_review_required, workflow_stage)"
        )
        player_rows = conn.exec_driver_sql("PRAGMA table_info(players)").fetchall()
        player_columns = {row[1] for row in player_rows}
        if player_rows and "subject_code" not in player_columns:
            conn.exec_driver_sql("ALTER TABLE players ADD COLUMN subject_code VARCHAR(64)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_players_subject_code ON players (subject_code)")
        task_rows = conn.exec_driver_sql("PRAGMA table_info(task_batches)").fetchall()
        task_columns = {row[1] for row in task_rows}
        if task_rows and "secondary_assigned_to" not in task_columns:
            conn.exec_driver_sql("ALTER TABLE task_batches ADD COLUMN secondary_assigned_to INTEGER REFERENCES users(id)")
        if task_rows and "selection_metadata" not in task_columns:
            conn.exec_driver_sql("ALTER TABLE task_batches ADD COLUMN selection_metadata JSON")
        if task_rows and "video_id" not in task_columns:
            conn.exec_driver_sql("ALTER TABLE task_batches ADD COLUMN video_id VARCHAR(36)")
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_task_batches_video_id ON task_batches (video_id)")
        if task_rows and "video_sha256" not in task_columns:
            conn.exec_driver_sql("ALTER TABLE task_batches ADD COLUMN video_sha256 VARCHAR(64)")
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_task_batches_video_sha256 ON task_batches (video_sha256)")
        if task_rows and "video_filename" not in task_columns:
            conn.exec_driver_sql("ALTER TABLE task_batches ADD COLUMN video_filename VARCHAR(512)")
        if task_rows and "match_format" not in task_columns:
            conn.exec_driver_sql("ALTER TABLE task_batches ADD COLUMN match_format VARCHAR(16)")
        frame_rows = conn.exec_driver_sql("PRAGMA table_info(batch_frames)").fetchall()
        frame_columns = {row[1] for row in frame_rows}
        if frame_rows and "timestamp_ms" not in frame_columns:
            conn.exec_driver_sql("ALTER TABLE batch_frames ADD COLUMN timestamp_ms BIGINT NOT NULL DEFAULT 0")


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
        logger.warning("Service will remain available and fall back to uniform frame extraction")



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

        username = settings.BOOTSTRAP_ADMIN_USERNAME.strip()
        password = settings.BOOTSTRAP_ADMIN_PASSWORD
        if not username or not password:
            logger.warning(
                "No super admin exists and bootstrap credentials are not configured; "
                "set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD"
            )
            return

        admin = db.query(User).filter(User.username == username).first()
        if not admin:
            admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            admin = User(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.SUPER_ADMIN,
                display_name="系统管理员",
                is_super_admin=True,
            )
            db.add(admin)
            logger.warning("Created configured bootstrap super admin '%s'", username)
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
app.include_router(research.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "badminton-management-backend",
        "ml_backend_enabled": settings.ENABLE_ML_BACKEND,
    }


@app.get("/api/ready")
def readiness_check():
    """Readiness probe: verifies the database, writable data paths and model state."""
    checks = {"database": False, "data_dir_writable": False, "pose_model": False}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        logger.exception("Readiness database check failed")

    try:
        probe = Path(settings.DATA_DIR) / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks["data_dir_writable"] = True
    except Exception:
        logger.exception("Readiness storage check failed")

    model = Path(settings.DATA_DIR) / "models" / YOLO_POSE_MODEL_NAME
    checks["pose_model"] = model.is_file() and model.stat().st_size > 0
    ready = checks["database"] and checks["data_dir_writable"]
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/api/config")
def get_config():
    """公开配置，供前端决定是否显示注册入口、ML 初标等。"""
    return {
        "allow_public_register": settings.ALLOW_PUBLIC_REGISTER,
        "ml_backend_enabled": settings.ENABLE_ML_BACKEND,
        "annotation_taxonomy": load_annotation_taxonomy(),
    }
