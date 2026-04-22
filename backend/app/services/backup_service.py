import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def create_backup_snapshot(sqlite_db_path: str, backup_dir: str, keep_count: int = 7) -> Path:
    db_path = Path(sqlite_db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    target_dir = Path(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = target_dir / f"badminton_{timestamp}.db"

    src_conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    _cleanup_old_backups(target_dir, keep_count)
    return backup_path


def _cleanup_old_backups(backup_dir: Path, keep_count: int) -> None:
    if keep_count <= 0:
        return

    backups = sorted(
        backup_dir.glob("badminton_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for stale_file in backups[keep_count:]:
        stale_file.unlink(missing_ok=True)


class BackupScheduler:
    def __init__(self, sqlite_db_path: str, backup_dir: str, interval_minutes: int, keep_count: int):
        self.sqlite_db_path = sqlite_db_path
        self.backup_dir = backup_dir
        self.interval_minutes = max(1, int(interval_minutes))
        self.keep_count = max(1, int(keep_count))
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="backup-scheduler", daemon=True)
        self._thread.start()
        logger.info(
            "Automatic backup scheduler started: every %d minutes, keep %d backups",
            self.interval_minutes,
            self.keep_count,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Automatic backup scheduler stopped")

    def _run(self) -> None:
        wait_seconds = self.interval_minutes * 60
        while not self._stop_event.wait(wait_seconds):
            try:
                backup_path = create_backup_snapshot(
                    sqlite_db_path=self.sqlite_db_path,
                    backup_dir=self.backup_dir,
                    keep_count=self.keep_count,
                )
                logger.info("Automatic backup created: %s", backup_path)
            except Exception as exc:
                logger.exception("Automatic backup failed: %s", exc)
