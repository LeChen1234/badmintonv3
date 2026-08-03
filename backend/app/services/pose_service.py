"""Production-oriented hybrid multi-person pose assistance.

YOLO supplies high-recall person proposals (including optional image tiles), then
MediaPipe refines each crop. Results are de-duplicated and mapped to the project's
23-point human skeleton. Racket/contact geometry is annotated separately.
"""

from __future__ import annotations

import logging
import math
import statistics
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.config import settings
from app.constants.keypoints import KEYPOINT_NAMES

logger = logging.getLogger(__name__)
_YOLO_MODEL = None
_YOLO_LOCK = threading.Lock()


class PoseBackendUnavailable(RuntimeError):
    """Raised when inference cannot run; distinct from a valid zero-person result."""


def _empty_keypoints_list():
    return [{"name": name, "x": 0, "y": 0, "visibility": 0} for name in KEYPOINT_NAMES]


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _point(name, xy, confidence, width, height):
    x = round(max(0.0, min(100.0, xy[0] / width * 100)), 2)
    y = round(max(0.0, min(100.0, xy[1] / height * 100)), 2)
    visibility = 2 if confidence >= 0.5 else 1 if confidence >= 0.15 else 0
    return {"name": name, "x": x, "y": y, "visibility": visibility}


def _coco_to_23(xy, conf, width, height):
    """Map COCO-17 to the stable 23-point human schema."""
    p = lambda i: (float(xy[i][0]), float(xy[i][1]))
    c = lambda i: float(conf[i]) if conf is not None else 1.0
    nose, ls, rs, lh, rh = p(0), p(5), p(6), p(11), p(12)
    shoulders, pelvis = _mid(ls, rs), _mid(lh, rh)
    torso_conf = min(c(5), c(6), c(11), c(12))
    eye_mid = _mid(p(1), p(2))
    head_top = (eye_mid[0], eye_mid[1] - max(2.0, abs(shoulders[1] - nose[1]) * 0.45))
    chin = (nose[0] * 0.65 + shoulders[0] * 0.35, nose[1] * 0.65 + shoulders[1] * 0.35)
    neck = (nose[0] * 0.25 + shoulders[0] * 0.75, nose[1] * 0.25 + shoulders[1] * 0.75)
    ltoe = (p(15)[0] + (p(15)[0] - p(13)[0]) * .18, p(15)[1] + (p(15)[1] - p(13)[1]) * .18)
    rtoe = (p(16)[0] + (p(16)[0] - p(14)[0]) * .18, p(16)[1] + (p(16)[1] - p(14)[1]) * .18)
    specs = [
        ("head_top", head_top, min(c(1), c(2))), ("head_center", nose, c(0)),
        ("chin", chin, min(c(0), c(5), c(6))), ("neck", neck, min(c(0), c(5), c(6))),
        ("chest_center", shoulders, min(c(5), c(6))), ("spine_mid", _mid(shoulders, pelvis), torso_conf),
        ("pelvis_center", pelvis, min(c(11), c(12))), ("left_shoulder", ls, c(5)),
        ("left_elbow", p(7), c(7)), ("left_wrist", p(9), c(9)), ("left_palm", p(9), c(9) * .7),
        ("right_shoulder", rs, c(6)), ("right_elbow", p(8), c(8)), ("right_wrist", p(10), c(10)),
        ("right_palm", p(10), c(10) * .7), ("left_hip", lh, c(11)), ("left_knee", p(13), c(13)),
        ("left_ankle", p(15), c(15)), ("left_toe", ltoe, min(c(13), c(15)) * .7),
        ("right_hip", rh, c(12)), ("right_knee", p(14), c(14)), ("right_ankle", p(16), c(16)),
        ("right_toe", rtoe, min(c(14), c(16)) * .7),
    ]
    return [_point(*s, width, height) for s in specs]


def _load_yolo():
    global _YOLO_MODEL
    if _YOLO_MODEL is not None:
        return _YOLO_MODEL
    with _YOLO_LOCK:
        if _YOLO_MODEL is None:
            from ultralytics import YOLO
            configured = Path(settings.POSE_YOLO_MODEL)
            model_path = configured if configured.is_absolute() else Path(settings.DATA_DIR) / "models" / configured
            _YOLO_MODEL = YOLO(str(model_path))
    return _YOLO_MODEL


def _infer_region(model, image, ox, oy, full_w, full_h, source):
    results = model.predict(
        image, conf=settings.POSE_YOLO_CONFIDENCE, iou=settings.POSE_YOLO_IOU,
        imgsz=settings.POSE_YOLO_IMAGE_SIZE, max_det=settings.POSE_MAX_PERSONS,
        classes=[0], verbose=False,
    )
    candidates = []
    for result in results:
        if result.boxes is None or result.keypoints is None:
            continue
        boxes = result.boxes.xyxy.cpu().numpy()
        scores = result.boxes.conf.cpu().numpy()
        key_xy = result.keypoints.xy.cpu().numpy()
        key_conf = result.keypoints.conf.cpu().numpy() if result.keypoints.conf is not None else None
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = [float(v) for v in box]
            xy = key_xy[i].copy()
            xy[:, 0] += ox; xy[:, 1] += oy
            bbox = [x1 + ox, y1 + oy, x2 + ox, y2 + oy]
            candidates.append({"bbox_px": bbox, "xy": xy, "conf": key_conf[i] if key_conf is not None else None,
                               "detection_confidence": float(scores[i]), "source": source})
    return candidates


def _iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    aa, bb = max(0, a[2] - a[0]) * max(0, a[3] - a[1]), max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return inter / max(aa + bb - inter, 1e-6)


def _intersection_over_smaller(a, b):
    """Return how much of the smaller box is covered by the intersection."""
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return intersection / max(min(area_a, area_b), 1e-6)


def _normalized_pose_distance(a, b):
    """Median matching-joint distance normalized by the smaller box diagonal."""
    distances = []
    conf_a, conf_b = a.get("conf"), b.get("conf")
    for index, (point_a, point_b) in enumerate(zip(a["xy"], b["xy"])):
        if conf_a is not None and float(conf_a[index]) < 0.15:
            continue
        if conf_b is not None and float(conf_b[index]) < 0.15:
            continue
        distances.append(math.hypot(float(point_a[0]) - float(point_b[0]), float(point_a[1]) - float(point_b[1])))
    if len(distances) < settings.POSE_MIN_VISIBLE_JOINTS:
        return float("inf")
    box_a, box_b = a["bbox_px"], b["bbox_px"]
    diagonal = min(math.hypot(box_a[2] - box_a[0], box_a[3] - box_a[1]),
                   math.hypot(box_b[2] - box_b[0], box_b[3] - box_b[1]))
    return statistics.median(distances) / max(diagonal, 1e-6)


def _same_person(a, b):
    if _iou(a["bbox_px"], b["bbox_px"]) >= settings.POSE_YOLO_IOU:
        return True
    return (
        _intersection_over_smaller(a["bbox_px"], b["bbox_px"]) >= settings.POSE_DEDUP_CONTAINMENT
        and _normalized_pose_distance(a, b) <= settings.POSE_DEDUP_KEYPOINT_DISTANCE
    )


def _nms(candidates):
    candidates = sorted(candidates, key=lambda c: c["detection_confidence"], reverse=True)
    kept = []
    for candidate in candidates:
        if all(not _same_person(candidate, old) for old in kept):
            kept.append(candidate)
    return kept[: settings.POSE_MAX_PERSONS]


def _select_candidates_for_box(candidates, target_box, limit):
    """Prefer the pose whose detector box best matches the annotator's box."""
    ranked = sorted(
        candidates,
        key=lambda candidate: (
            _iou(candidate["bbox_px"], target_box),
            candidate["detection_confidence"],
        ),
        reverse=True,
    )
    return ranked[:limit]


def predict_persons_detailed_from_image_path(
    image_path: Union[str, Path], bbox_percent: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    import cv2
    image = cv2.imread(str(image_path))
    if image is None:
        return []
    height, width = image.shape[:2]
    work_image = image
    offset_x = offset_y = 0
    target_box_px = None
    if bbox_percent is not None:
        if len(bbox_percent) != 4:
            raise ValueError("bbox_percent must contain x, y, width and height")
        bx, by, bw, bh = bbox_percent
        raw_x1 = max(0, min(width - 1, int(bx / 100 * width)))
        raw_y1 = max(0, min(height - 1, int(by / 100 * height)))
        raw_x2 = max(raw_x1 + 1, min(width, int((bx + bw) / 100 * width)))
        raw_y2 = max(raw_y1 + 1, min(height, int((by + bh) / 100 * height)))
        target_box_px = [raw_x1, raw_y1, raw_x2, raw_y2]
        padding_x = int((raw_x2 - raw_x1) * settings.POSE_BOX_PADDING_RATIO)
        padding_y = int((raw_y2 - raw_y1) * settings.POSE_BOX_PADDING_RATIO)
        offset_x = max(0, raw_x1 - padding_x)
        offset_y = max(0, raw_y1 - padding_y)
        end_x = min(width, raw_x2 + padding_x)
        end_y = min(height, raw_y2 + padding_y)
        work_image = image[offset_y:end_y, offset_x:end_x]
    try:
        model = _load_yolo()
        candidates = _infer_region(model, work_image, offset_x, offset_y, width, height, "yolo-box" if bbox_percent else "yolo-full")
        if bbox_percent is None and settings.POSE_ENABLE_TILING and min(width, height) >= settings.POSE_TILE_MIN_SIDE:
            tile_w, tile_h = int(width * .62), int(height * .62)
            for x in sorted(set((0, width - tile_w))):
                for y in sorted(set((0, height - tile_h))):
                    candidates += _infer_region(model, image[y:y+tile_h, x:x+tile_w], x, y, width, height, "yolo-tile")
        candidates = _nms(candidates)
        if target_box_px is not None:
            candidates = _select_candidates_for_box(candidates, target_box_px, settings.POSE_BOX_MAX_PERSONS)
    except Exception as exc:
        logger.exception("YOLO multi-person pose failed: %s", exc)
        raise PoseBackendUnavailable(
            "多人姿态模型不可用，请检查 ultralytics、PyTorch 与 POSE_YOLO_MODEL 配置"
        ) from exc

    persons = []
    for candidate in candidates:
        keypoints = _coco_to_23(candidate["xy"], candidate["conf"], width, height)
        visible = sum(p["visibility"] > 0 for p in keypoints)
        if visible < settings.POSE_MIN_VISIBLE_JOINTS:
            continue
        x1, y1, x2, y2 = candidate["bbox_px"]
        persons.append({
            "keypoints": keypoints,
            "bbox": [round(x1 / width * 100, 2), round(y1 / height * 100, 2),
                     round((x2-x1) / width * 100, 2), round((y2-y1) / height * 100, 2)],
            "detection_confidence": round(candidate["detection_confidence"], 4),
            "visible_keypoints": visible,
            "source": candidate["source"],
        })
    return sorted(persons, key=lambda p: (p["bbox"][0], p["bbox"][1]))


def predict_keypoints_multi_from_image_path(image_path):
    return [person["keypoints"] for person in predict_persons_detailed_from_image_path(image_path)]


def predict_keypoints_from_image_path(image_path):
    persons = predict_keypoints_multi_from_image_path(image_path)
    return persons[0] if persons else _empty_keypoints_list()
