"""上传图片/视频并提取帧，保存到 UPLOAD_DIR。"""

import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import BinaryIO, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.batch_frame import BatchFrame
from app.models.task_batch import MediaProcessStatus, TaskBatch
from app.services import task_service

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
PROCESSING_DIR_NAME = "_processing"


def _batch_upload_dir(batch_id: int) -> Path:
    d = Path(settings.UPLOAD_DIR) / f"batch_{batch_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _batch_processing_dir(batch_id: int) -> Path:
    return _batch_upload_dir(batch_id) / PROCESSING_DIR_NAME


def _batch_chunk_upload_dir(batch_id: int, upload_id: str) -> Path:
    return _batch_processing_dir(batch_id) / "chunks" / upload_id


def get_uploaded_chunks(batch_id: int, upload_id: str) -> List[int]:
    chunk_dir = _batch_chunk_upload_dir(batch_id, upload_id)
    if not chunk_dir.exists():
        return []
    chunks = []
    for p in chunk_dir.glob("*.part"):
        try:
            chunks.append(int(p.stem))
        except ValueError:
            pass
    return sorted(chunks)


def cleanup_processing_dir(batch_id: int) -> None:
    shutil.rmtree(_batch_processing_dir(batch_id), ignore_errors=True)


def _save_uploaded_images(
    batch_id: int,
    files: List[Tuple[bytes, str]],
) -> List[Tuple[int, str]]:
    """保存多张图片，返回 [(frame_index, file_path), ...]"""
    base = _batch_upload_dir(batch_id)
    results = []
    for i, (content, filename) in enumerate(files, start=1):
        ext = Path(filename).suffix.lower() or ".jpg"
        if ext not in ALLOWED_IMAGE_EXT:
            ext = ".jpg"
        path = base / f"frame_{i}{ext}"
        path.write_bytes(content)
        rel = f"batch_{batch_id}/frame_{i}{ext}"
        results.append((i, rel))
    return results


def _extract_frames_from_video(video_path: Path, out_dir: Path, max_frames: int = 500) -> List[Path]:
    """使用 opencv 从视频提取帧，保存到 out_dir，返回保存的文件路径列表。"""
    try:
        import cv2
    except ImportError:
        logger.warning("opencv not installed, cannot extract video frames")
        return []

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("Could not open video: %s", video_path)
        return []

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total <= 0:
        total = 1000
    step = max(1, total // max_frames) if total > max_frames else 1
    saved = []
    frame_idx = 0
    out_idx = 1

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0 and out_idx <= max_frames:
            out_path = out_dir / f"frame_{out_idx}.jpg"
            cv2.imwrite(str(out_path), frame)
            saved.append(out_path)
            out_idx += 1
        frame_idx += 1

    cap.release()
    return saved


def _extract_video_to_paths(
    video_path: Path,
    out_dir: Path,
    *,
    max_frames: int = 500,
    use_yolo: bool = False,
    motion_percentile: Optional[float] = None,
) -> List[Path]:
    if use_yolo:
        from app.services.yolo_preprocess_service import extract_and_filter_video

        return extract_and_filter_video(
            video_path,
            out_dir,
            target_fps=10.0,
            motion_percentile=motion_percentile,
            max_frames=max_frames,
        )
    return _extract_frames_from_video(video_path, out_dir, max_frames=max_frames)


def stage_uploaded_video(batch_id: int, content: bytes, filename: str) -> Path:
    processing_dir = _batch_processing_dir(batch_id)
    cleanup_processing_dir(batch_id)
    processing_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower() or ".mp4"
    video_path = processing_dir / f"source{ext}"
    video_path.write_bytes(content)
    return video_path


def save_video_chunk(
    batch_id: int,
    *,
    upload_id: str,
    chunk_index: int,
    total_chunks: int,
    chunk_stream: BinaryIO,
    original_filename: str,
) -> bool:
    """保存视频分块；当分块齐全时自动合并并返回 True。"""
    processing_dir = _batch_processing_dir(batch_id)
    processing_dir.mkdir(parents=True, exist_ok=True)

    chunk_dir = _batch_chunk_upload_dir(batch_id, upload_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    part_path = chunk_dir / f"{chunk_index:06d}.part"
    with part_path.open("wb") as dst:
        shutil.copyfileobj(chunk_stream, dst, length=1024 * 1024)

    ready = all((chunk_dir / f"{i:06d}.part").exists() for i in range(total_chunks))
    if not ready:
        return False

    ext = Path(original_filename).suffix.lower() or ".mp4"
    target_video = processing_dir / f"source{ext}"
    if target_video.exists():
        target_video.unlink()

    with target_video.open("wb") as dst:
        for i in range(total_chunks):
            current_part = chunk_dir / f"{i:06d}.part"
            with current_part.open("rb") as src:
                shutil.copyfileobj(src, dst, length=1024 * 1024)

    shutil.rmtree(chunk_dir, ignore_errors=True)
    return True


def _clear_batch_media_files(batch_id: int) -> None:
    batch_dir = _batch_upload_dir(batch_id)
    for path in batch_dir.iterdir():
        if path.name == PROCESSING_DIR_NAME:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def _promote_processed_frames(batch_id: int, saved_paths: List[Path]) -> List[Tuple[int, str]]:
    batch_dir = _batch_upload_dir(batch_id)
    _clear_batch_media_files(batch_id)

    entries: List[Tuple[int, str]] = []
    for i, path in enumerate(saved_paths, start=1):
        ext = path.suffix.lower() or ".jpg"
        final_path = batch_dir / f"frame_{i}{ext}"
        shutil.move(str(path), str(final_path))
        entries.append((i, f"batch_{batch_id}/{final_path.name}"))

    cleanup_processing_dir(batch_id)
    return entries


def process_uploaded_video_in_background(
    batch_id: int,
    *,
    max_frames: int,
    use_yolo: bool,
    motion_percentile: Optional[float],
    source_name: str,
) -> None:
    db = SessionLocal()
    try:
        batch = db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()
        if not batch:
            cleanup_processing_dir(batch_id)
            return

        task_service.update_media_process_state(
            db,
            batch,
            MediaProcessStatus.PROCESSING,
            message=f"正在后台处理视频：{source_name}",
            started_at=datetime.utcnow(),
            finished_at=None,
        )

        processing_dir = _batch_processing_dir(batch_id)
        video_candidates = [p for p in processing_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_VIDEO_EXT]
        if not video_candidates:
            raise RuntimeError("未找到待处理的视频文件")

        video_path = video_candidates[0]
        frames_dir = processing_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = _extract_video_to_paths(
            video_path,
            frames_dir,
            max_frames=max_frames,
            use_yolo=use_yolo,
            motion_percentile=motion_percentile,
        )
        if not saved_paths:
            raise RuntimeError("未提取到任何帧，请检查视频内容或参数设置")

        entries = _promote_processed_frames(batch_id, saved_paths)
        batch = db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()
        if not batch:
            cleanup_processing_dir(batch_id)
            return

        replace_frames_for_batch(db, batch, entries)
        task_service.update_media_process_state(
            db,
            batch,
            MediaProcessStatus.COMPLETED,
            message=f"视频处理完成，已提取 {len(entries)} 帧。",
            started_at=batch.media_process_started_at,
            finished_at=datetime.utcnow(),
        )
    except Exception as exc:
        logger.exception("后台处理视频失败: batch_id=%s", batch_id)
        db.rollback()
        batch = db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()
        if batch:
            task_service.update_media_process_state(
                db,
                batch,
                MediaProcessStatus.FAILED,
                message=f"视频处理失败：{exc}",
                started_at=batch.media_process_started_at,
                finished_at=datetime.utcnow(),
            )
        cleanup_processing_dir(batch_id)
    finally:
        db.close()


def save_uploaded_video(
    batch_id: int,
    content: bytes,
    filename: str,
    max_frames: int = 500,
    use_yolo: bool = False,
    motion_percentile: float | None = None,
) -> List[Tuple[int, str]]:
    """保存上传的视频并提取帧，返回 [(frame_index, file_path), ...]。

    use_yolo=True 且 motion_percentile 不为 None 时，先计算帧间动作分数，
    再按百分位动态阈值筛选；否则均匀抽帧。
    """
    video_path = stage_uploaded_video(batch_id, content, filename)
    frames_dir = _batch_processing_dir(batch_id) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = _extract_video_to_paths(
        video_path,
        frames_dir,
        max_frames=max_frames,
        use_yolo=use_yolo,
        motion_percentile=motion_percentile,
    )
    return _promote_processed_frames(batch_id, saved_paths)


def add_frames_to_batch(
    db: Session,
    batch: TaskBatch,
    frame_entries: List[Tuple[int, str]],
) -> int:
    """将帧记录写入 BatchFrame 并更新 batch.total_frames。可追加或覆盖。"""
    existing = db.query(BatchFrame).filter(BatchFrame.task_batch_id == batch.id).all()
    max_idx = max((f.frame_index for f in existing), default=0)

    for i, (frame_index, file_path) in enumerate(frame_entries, start=1):
        idx = max_idx + i
        bf = BatchFrame(task_batch_id=batch.id, frame_index=idx, file_path=file_path)
        db.add(bf)

    batch.total_frames = max_idx + len(frame_entries)
    db.commit()
    return len(frame_entries)


def replace_frames_for_batch(
    db: Session,
    batch: TaskBatch,
    frame_entries: List[Tuple[int, str]],
) -> int:
    """替换该批次所有帧（先删后加），更新 total_frames。"""
    db.query(BatchFrame).filter(BatchFrame.task_batch_id == batch.id).delete()
    for i, (_, file_path) in enumerate(frame_entries, start=1):
        bf = BatchFrame(task_batch_id=batch.id, frame_index=i, file_path=file_path)
        db.add(bf)
    batch.total_frames = len(frame_entries)
    db.commit()
    return len(frame_entries)
