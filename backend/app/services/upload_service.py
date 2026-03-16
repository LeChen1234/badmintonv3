"""上传图片/视频并提取帧，保存到 UPLOAD_DIR。"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.batch_frame import BatchFrame
from app.models.task_batch import TaskBatch

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}


def _batch_upload_dir(batch_id: int) -> Path:
    d = Path(settings.UPLOAD_DIR) / f"batch_{batch_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


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


def save_uploaded_video(
    batch_id: int,
    content: bytes,
    filename: str,
    max_frames: int = 1000000,
    use_yolo: bool = False,
    motion_threshold: float | None = None,
) -> List[Tuple[int, str]]:
    """保存上传的视频并提取帧，返回 [(frame_index, file_path), ...]。

    use_yolo=True 且 motion_threshold 不为 None 时，使用 YOLOv8 骨架分析
    只保留帧间动作幅度 >= motion_threshold 的帧；否则均匀抽帧。
    """
    base = _batch_upload_dir(batch_id)
    ext = Path(filename).suffix.lower() or ".mp4"
    video_path = base / f"video{ext}"
    video_path.write_bytes(content)

    if use_yolo:
        logger.info("使用 YOLOv8 骨架分析提取帧，motion_threshold=%.2f", motion_threshold)
        from app.services.yolo_preprocess_service import extract_and_filter_video
        saved_paths = extract_and_filter_video(
            video_path,
            base,
            target_fps=10.0,
            motion_threshold=motion_threshold,
            max_frames=max_frames,
        )
    else:
        saved_paths = _extract_frames_from_video(video_path, base, max_frames=max_frames)

    rel_prefix = f"batch_{batch_id}/"
    return [(i, rel_prefix + p.name) for i, p in enumerate(saved_paths, start=1)]


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
