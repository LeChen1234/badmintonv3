"""YOLO 视频预处理服务：以目标帧率抽帧，计算人体关节点帧间欧氏距离，
按动作幅度阈值过滤，只保留动作变化明显的帧写入磁盘。

若 ultralytics 未安装或模型不存在，自动降级为纯 OpenCV 均匀抽帧，
不会抛异常，只记录警告日志。
"""

import logging
import math
from pathlib import Path
from typing import List, Optional, Tuple

import cv2

from app.config import PROJECT_ROOT, settings

logger = logging.getLogger(__name__)

# COCO 身体关键点索引（去掉 0-4 头部）
_BODY_KPT_INDICES = list(range(5, 17))


def _find_yolo_model() -> Optional[Path]:
    """按优先级查找 yolov8n-pose.pt：data/models → 项目根目录。"""
    candidates = [
        Path(settings.DATA_DIR) / "models" / "yolov8n-pose.pt",
        PROJECT_ROOT / "yolov8n-pose.pt",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _centroid_x(kpts_xy) -> float:
    """用 5-16 号关节点的非零 x 均值作为人物中心，用于左右排序。"""
    xs = [float(k[0]) for k in kpts_xy[5:17] if float(k[0]) > 0]
    return sum(xs) / len(xs) if xs else 0.0


def _motion_score_between(prev_kpts, curr_kpts) -> Tuple[float, int]:
    """计算两帧同一人之间的关节点欧氏距离之和，返回 (总距离, 有效关节数)。"""
    total = 0.0
    count = 0
    for idx in _BODY_KPT_INDICES:
        px, py = float(prev_kpts[idx][0]), float(prev_kpts[idx][1])
        cx, cy = float(curr_kpts[idx][0]), float(curr_kpts[idx][1])
        if px > 0 and py > 0 and cx > 0 and cy > 0:
            total += math.hypot(cx - px, cy - py)
            count += 1
    return total, count


def extract_and_filter_video(
    video_path: Path,
    out_dir: Path,
    *,
    target_fps: float = 10.0,
    motion_threshold: Optional[float] = None,
    min_people: int = 2,
    min_shared_joints: int = 8,
    max_frames: int = 2000,
) -> List[Path]:
    """从视频抽帧，写入 out_dir，返回保存路径列表。

    参数
    ----
    target_fps:        期望抽帧帧率，默认 10 FPS。
    motion_threshold:  帧间动作幅度（欧氏距离之和）最小值；None 表示不过滤，
                       保留全部 target_fps 抽样帧。
    min_people:        有效帧最少人数（仅在启用 motion_threshold 时生效）。
    min_shared_joints: 两帧间至少有几个共同可见关节才计分。
    max_frames:        输出帧数上限。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 无需过滤 → 直接均匀抽帧，无需 YOLO
    if motion_threshold is None:
        return _plain_extract(video_path, out_dir, target_fps, max_frames)

    # 需要过滤 → 尝试加载 YOLO
    model_path = _find_yolo_model()
    if model_path is None:
        logger.warning(
            "yolo_preprocess: 未找到 yolov8n-pose.pt（已查找 data/models/ 与项目根目录），"
            "降级为均匀抽帧（不过滤）。"
        )
        return _plain_extract(video_path, out_dir, target_fps, max_frames)

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.warning("yolo_preprocess: ultralytics 未安装，降级为均匀抽帧（不过滤）。")
        return _plain_extract(video_path, out_dir, target_fps, max_frames)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("yolo_preprocess: 无法打开视频 %s", video_path)
        return []

    try:
        logger.info(
            "yolo_preprocess: 开始处理 %s  target_fps=%.1f threshold=%.2f min_people=%d",
            video_path.name, target_fps, motion_threshold, min_people,
        )
        original_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        time_interval = 1.0 / max(0.1, target_fps)
        logger.info("yolo_preprocess: 加载模型 %s", model_path.name)
        model = YOLO(str(model_path))

        saved: List[Path] = []
        prev_valid_kpts: Optional[list] = None  # 上一有效帧的 kpts 列表（已按 x 排序）
        out_idx = 0
        frame_count = 0
        next_process_time = 0.0

        # while cap.isOpened() and out_idx < max_frames:
        while cap.isOpened(): # 若 yolo 过滤则不限制帧数
            ok, frame = cap.read()
            if not ok:
                break

            current_time = frame_count / original_fps
            if current_time >= next_process_time:
                # YOLO 推理
                results = model.predict(frame, conf=0.5, verbose=False)
                kpts_list: list = []
                if results[0].keypoints is not None and len(results[0].keypoints) > 0:
                    raw = results[0].keypoints.xy.cpu().numpy()
                    # 按左右顺序排列，保证相邻帧配对稳定
                    kpts_list = sorted(raw, key=_centroid_x)

                people_count = len(kpts_list)
                if people_count >= min_people:
                    if prev_valid_kpts is None:
                        # 第一个有效帧：仅作基准，不写出（没有前帧可比较）
                        prev_valid_kpts = kpts_list
                    else:
                        pair_count = min(len(prev_valid_kpts), len(kpts_list))
                        total_score = 0.0
                        total_joints = 0
                        for pi in range(pair_count):
                            d, cnt = _motion_score_between(prev_valid_kpts[pi], kpts_list[pi])
                            total_score += d
                            total_joints += cnt

                        if total_joints >= min_shared_joints and total_score >= motion_threshold:
                            out_path = out_dir / f"frame_{out_idx:08d}.jpg"
                            cv2.imwrite(str(out_path), frame)
                            saved.append(out_path)
                            out_idx += 1

                        prev_valid_kpts = kpts_list

                next_process_time += time_interval
            frame_count += 1

        return saved

    finally:
        logger.info("yolo_preprocess: 完成，保存帧数=%d", len(saved))
        cap.release()


def _plain_extract(
    video_path: Path,
    out_dir: Path,
    target_fps: float,
    max_frames: int,
) -> List[Path]:
    """不使用 YOLO、按时间间隔均匀抽帧的降级实现。"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("yolo_preprocess._plain_extract: 无法打开视频 %s", video_path)
        return []

    try:
        original_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        time_interval = 1.0 / max(0.1, target_fps)
        next_process_time = 0.0
        frame_count = 0
        out_idx = 0
        saved: List[Path] = []

        while cap.isOpened() and out_idx < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            current_time = frame_count / original_fps
            if current_time >= next_process_time:
                out_path = out_dir / f"frame_{out_idx:08d}.jpg"
                cv2.imwrite(str(out_path), frame)
                saved.append(out_path)
                out_idx += 1
                next_process_time += time_interval
            frame_count += 1

        return saved

    finally:
        cap.release()
