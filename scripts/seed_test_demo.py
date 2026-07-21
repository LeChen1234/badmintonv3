"""Create a deterministic local demo task in the isolated test database."""
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models.batch_frame import BatchFrame
from app.models.player import Player
from app.models.project import Project
from app.models.task_batch import MediaProcessStatus, TaskBatch, TaskStatus
from app.models.user import User


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(TaskBatch).first():
            return
        admin = db.query(User).filter(User.username == "admin").first()
        if admin is None:
            raise RuntimeError("test administrator is missing")
        project = Project(name="羽毛球视频标注测试", description="本地交互验收数据", created_by=admin.id)
        db.add(project)
        db.flush()
        batch = TaskBatch(
            project_id=project.id, name="多人比赛视频标注", assigned_to=admin.id,
            status=TaskStatus.ANNOTATING, total_frames=1,
            media_process_status=MediaProcessStatus.COMPLETED.value,
            metadata_confirmed=True, match_name="本地测试比赛", match_format="singles",
        )
        db.add(batch)
        db.flush()
        db.add_all([
            Player(task_batch_id=batch.id, name="选手 A", subject_code="PLAYER_A"),
            Player(task_batch_id=batch.id, name="选手 B", subject_code="PLAYER_B"),
        ])
        source = Path(settings.UPLOAD_DIR) / "batch_1" / "frame_1.jpeg"
        if not source.exists():
            fallback = Path(settings.UPLOAD_DIR) / "batch_1" / "frame_1.jpg"
            source = fallback if fallback.exists() else source
        db.add(BatchFrame(
            task_batch_id=batch.id, frame_index=1,
            file_path=str(source.relative_to(Path(settings.UPLOAD_DIR))).replace("\\", "/"),
            timestamp_ms=12_340,
        ))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
