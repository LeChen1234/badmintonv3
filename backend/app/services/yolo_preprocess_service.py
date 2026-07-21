"""YOLO 视频预处理服务：以目标帧率抽帧，计算人体关节点帧间欧氏距离，
先得到该视频的动作分数分布，再按百分位动态计算阈值后筛帧写盘。

若 ultralytics 未安装或模型不存在，自动降级为纯 OpenCV 均匀抽帧，
不会抛异常，只记录警告日志。
"""

import logging
import math
import shutil
from itertools import permutations
from pathlib import Path
from time import monotonic
from typing import Callable, List, Optional, Tuple

import cv2

from app.config import settings
from app.services.information_selection_service import diverse_indices, score_motion_sequence

logger = logging.getLogger(__name__)

# COCO 身体关键点索引（去掉 0-4 头部）
_BODY_KPT_INDICES = list(range(5, 17))
ProgressCallback = Callable[[str, int, int], None]


def _find_yolo_model() -> Optional[Path]:
    """查找 data/models 下的 yolov8n-pose.pt。"""
    candidates = [Path(settings.DATA_DIR) / "models" / "yolov8n-pose.pt"]
    for p in candidates:
        if p.exists():
            return p
    return None


def _visible_body_points(kpts_xy) -> List[Tuple[float, float]]:
    """返回有效身体关键点；YOLO 以 (0, 0) 表示不可见点。"""
    return [
        (float(kpts_xy[i][0]), float(kpts_xy[i][1]))
        for i in _BODY_KPT_INDICES
        if float(kpts_xy[i][0]) > 0 and float(kpts_xy[i][1]) > 0
    ]


def _person_geometry(kpts_xy) -> Optional[Tuple[float, float, float]]:
    """返回人物中心和尺度（身体关键点包围盒对角线）。"""
    points = _visible_body_points(kpts_xy)
    if len(points) < 2:
        return None
    xs, ys = zip(*points)
    scale = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if scale <= 1e-6:
        return None
    return sum(xs) / len(xs), sum(ys) / len(ys), scale


def _motion_score_between(prev_kpts, curr_kpts) -> Tuple[float, int]:
    """计算尺度归一化位移和，避免分辨率和拍摄距离改变阈值含义。"""
    prev_geometry = _person_geometry(prev_kpts)
    curr_geometry = _person_geometry(curr_kpts)
    if prev_geometry is None or curr_geometry is None:
        return 0.0, 0
    scale = (prev_geometry[2] + curr_geometry[2]) / 2.0
    total = 0.0
    count = 0
    for idx in _BODY_KPT_INDICES:
        px, py = float(prev_kpts[idx][0]), float(prev_kpts[idx][1])
        cx, cy = float(curr_kpts[idx][0]), float(curr_kpts[idx][1])
        if px > 0 and py > 0 and cx > 0 and cy > 0:
            total += math.hypot(cx - px, cy - py) / scale
            count += 1
    return total, count


def _match_people(prev_people, curr_people) -> List[Tuple[object, object]]:
    """按归一化中心距离做一对一匹配，而不是依赖容易交换的左右次序。"""
    if not prev_people or not curr_people:
        return []
    if len(prev_people) <= len(curr_people):
        left, right, swapped = prev_people, curr_people, False
    else:
        left, right, swapped = curr_people, prev_people, True

    def pair_cost(a, b) -> Optional[float]:
        ga, gb = _person_geometry(a), _person_geometry(b)
        if ga is None or gb is None:
            return None
        return math.hypot(ga[0] - gb[0], ga[1] - gb[1]) / ((ga[2] + gb[2]) / 2.0)

    if len(right) > 6:
        candidates = []
        for i, a in enumerate(left):
            for j, b in enumerate(right):
                cost = pair_cost(a, b)
                if cost is not None:
                    candidates.append((cost, i, j))
        used_left, used_right, pairs = set(), set(), []
        for _, i, j in sorted(candidates):
            if i not in used_left and j not in used_right:
                pairs.append((left[i], right[j]))
                used_left.add(i)
                used_right.add(j)
        return [(b, a) for a, b in pairs] if swapped else pairs

    best = None
    for candidate in permutations(range(len(right)), len(left)):
        cost = 0.0
        valid = True
        for i, j in enumerate(candidate):
            current_cost = pair_cost(left[i], right[j])
            if current_cost is None:
                valid = False
                break
            cost += current_cost
        if valid and (best is None or cost < best[0]):
            best = (cost, candidate)
    if best is None:
        return []
    pairs = [(left[i], right[j]) for i, j in enumerate(best[1])]
    return [(b, a) for a, b in pairs] if swapped else pairs


def _percentile(values: List[float], q: float) -> float:
    """计算百分位（线性插值），q 取值范围 [0, 100]。"""
    if not values:
        return 0.0
    q = max(0.0, min(100.0, float(q)))
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def extract_and_filter_video(
    video_path: Path,
    out_dir: Path,
    *,
    target_fps: float = 10.0,
    motion_percentile: Optional[float] = None,
    min_people: int = 2,
    min_shared_joints: int = 8,
    max_frames: int = 2000,
    progress_callback: Optional[ProgressCallback] = None,
    information_weights: Optional[dict] = None,
) -> List[Path]:
    """从视频抽帧，写入 out_dir，返回保存路径列表。

    参数
    ----
    target_fps:        期望抽帧帧率，默认 10 FPS。
    motion_percentile: 帧间动作分数的百分位阈值（如 90 表示保留 >= P90 的帧）；
                       None 表示不过滤，保留全部 target_fps 抽样帧。
    min_people:        有效帧最少人数（仅在启用 motion_percentile 时生效）。
    min_shared_joints: 两帧间至少有几个共同可见关节才计分。
    max_frames:        输出帧数上限。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if motion_percentile is None:
        return _plain_extract(video_path, out_dir, target_fps, max_frames, progress_callback=progress_callback)

    # 需要过滤 → 尝试加载 YOLO
    model_path = _find_yolo_model()
    if model_path is None:
        logger.warning(
            "yolo_preprocess: 未找到 yolov8n-pose.pt（已查找 data/models/），"
            "降级为均匀抽帧（不过滤）。"
        )
        return _plain_extract(video_path, out_dir, target_fps, max_frames, progress_callback=progress_callback)

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.warning("yolo_preprocess: ultralytics 未安装，降级为均匀抽帧（不过滤）。")
        return _plain_extract(video_path, out_dir, target_fps, max_frames, progress_callback=progress_callback)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("yolo_preprocess: 无法打开视频 %s", video_path)
        return []

    saved: List[Path] = []
    candidate_dir: Optional[Path] = None
    try:
        logger.info(
            "yolo_preprocess: 开始处理 %s target_fps=%.1f percentile=P%.1f min_people=%d",
            video_path.name,
            target_fps,
            motion_percentile,
            min_people,
        )
        original_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        time_interval = 1.0 / max(0.1, target_fps)
        logger.info("yolo_preprocess: 加载模型 %s", model_path.name)
        model = YOLO(str(model_path))

        candidate_dir = out_dir / "_candidates"
        shutil.rmtree(candidate_dir, ignore_errors=True)
        candidate_dir.mkdir(parents=True, exist_ok=True)

        candidate_paths_and_scores: List[Tuple[Path, float, int]] = []
        prev_valid_kpts: Optional[list] = None
        frame_count = 0
        candidate_idx = 0
        next_process_time = 0.0
        last_progress_tick = 0.0

        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break

            if progress_callback and total_source_frames > 0:
                now = monotonic()
                processed = min(frame_count + 1, total_source_frames)
                if processed == 1 or processed >= total_source_frames or (now - last_progress_tick) >= 1.0:
                    progress_callback("infer", processed, total_source_frames)
                    last_progress_tick = now

            current_time = frame_count / original_fps
            if current_time >= next_process_time:
                # YOLO 推理
                results = model.predict(frame, conf=0.5, verbose=False)
                kpts_list: list = []
                if results[0].keypoints is not None and len(results[0].keypoints) > 0:
                    raw = results[0].keypoints.xy.cpu().numpy()
                    kpts_list = list(raw)

                people_count = len(kpts_list)
                if people_count >= min_people:
                    if prev_valid_kpts is None:
                        prev_valid_kpts = kpts_list
                    else:
                        total_score = 0.0
                        total_joints = 0
                        for prev_person, curr_person in _match_people(prev_valid_kpts, kpts_list):
                            d, cnt = _motion_score_between(prev_person, curr_person)
                            total_score += d
                            total_joints += cnt

                        if total_joints >= min_shared_joints:
                            timestamp_ms = int(round(current_time * 1000))
                            cand_path = candidate_dir / f"candidate_{candidate_idx:08d}_t{timestamp_ms}.jpg"
                            cv2.imwrite(str(cand_path), frame)
                            candidate_paths_and_scores.append((cand_path, total_score / total_joints, timestamp_ms))
                            candidate_idx += 1

                        prev_valid_kpts = kpts_list
                else:
                    prev_valid_kpts = None

                next_process_time += time_interval
            frame_count += 1

        if progress_callback and total_source_frames > 0:
            progress_callback("infer", total_source_frames, total_source_frames)

        if not candidate_paths_and_scores:
            return []

        raw_motion = [score for _, score, _ in candidate_paths_and_scores]
        information_rows = score_motion_sequence(raw_motion, weights=information_weights)
        information_scores = [row["score"] for row in information_rows]
        threshold = _percentile(information_scores, motion_percentile)
        selected_indices = set(diverse_indices(information_scores, threshold, min_gap=2))
        logger.info(
            "yolo_preprocess: frame selection completed percentile=P%.1f threshold=%.3f candidates=%d selected=%d",
            motion_percentile,
            threshold,
            len(candidate_paths_and_scores),
            len(selected_indices),
        )

        for zero_index, (cand_path, _raw_score, timestamp_ms) in enumerate(candidate_paths_and_scores):
            current_idx = zero_index + 1
            if progress_callback:
                progress_callback("filter", current_idx, len(candidate_paths_and_scores))
            if zero_index not in selected_indices:
                continue
            out_path = out_dir / f"frame_{len(saved):08d}_t{timestamp_ms}.jpg"
            shutil.move(str(cand_path), str(out_path))
            saved.append(out_path)
            if len(saved) >= max_frames:
                break

        if progress_callback and candidate_paths_and_scores:
            progress_callback("filter", len(candidate_paths_and_scores), len(candidate_paths_and_scores))

        return saved

    finally:
        if candidate_dir is not None:
            shutil.rmtree(candidate_dir, ignore_errors=True)
        logger.info("yolo_preprocess: 完成，保存帧数=%d", len(saved))
        cap.release()


def _plain_extract(
    video_path: Path,
    out_dir: Path,
    target_fps: float,
    max_frames: int,
    progress_callback: Optional[ProgressCallback] = None,
) -> List[Path]:
    """不使用 YOLO、按时间间隔均匀抽帧的降级实现。"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        logger.warning("yolo_preprocess._plain_extract: 无法打开视频 %s", video_path)
        return []

    try:
        original_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        time_interval = 1.0 / max(0.1, target_fps)
        next_process_time = 0.0
        frame_count = 0
        out_idx = 0
        saved: List[Path] = []
        last_progress_tick = 0.0

        while cap.isOpened() and out_idx < max_frames:
            ok, frame = cap.read()
            if not ok:
                break

            if progress_callback and total_source_frames > 0:
                now = monotonic()
                processed = min(frame_count + 1, total_source_frames)
                if processed == 1 or processed >= total_source_frames or (now - last_progress_tick) >= 1.0:
                    progress_callback("plain", processed, total_source_frames)
                    last_progress_tick = now

            current_time = frame_count / original_fps
            if current_time >= next_process_time:
                timestamp_ms = int(round(current_time * 1000))
                out_path = out_dir / f"frame_{out_idx:08d}_t{timestamp_ms}.jpg"
                cv2.imwrite(str(out_path), frame)
                saved.append(out_path)
                out_idx += 1
                next_process_time += time_interval
            frame_count += 1

        if progress_callback and total_source_frames > 0:
            progress_callback("plain", total_source_frames, total_source_frames)

        return saved

    finally:
        cap.release()
