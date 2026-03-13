"""关节点预测：支持单人（MediaPipe Pose）与多人（PoseLandmarker）。映射到项目 25 点骨架。"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from app.config import settings
from app.constants.keypoints import KEYPOINT_NAMES

logger = logging.getLogger(__name__)

# MediaPipe 33 点索引
class MP:
    NOSE = 0
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


def _mid(a: tuple, b: tuple) -> tuple:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _landmarks_to_our_25(lm) -> List[Dict[str, Any]]:
    """将一人的 33 个 MediaPipe 关节点转为 25 点（0–100%，含球拍两点 0）。"""
    L = lambda i: (lm[i].x, lm[i].y)
    nose = L(MP.NOSE)
    mouth_mid = _mid(L(MP.MOUTH_LEFT), L(MP.MOUTH_RIGHT))
    l_shoulder = L(MP.LEFT_SHOULDER)
    r_shoulder = L(MP.RIGHT_SHOULDER)
    shoulder_mid = _mid(l_shoulder, r_shoulder)
    l_hip = L(MP.LEFT_HIP)
    r_hip = L(MP.RIGHT_HIP)
    pelvis = _mid(l_hip, r_hip)
    spine_mid = _mid(shoulder_mid, pelvis)
    neck = (0.4 * nose[0] + 0.6 * shoulder_mid[0], 0.4 * nose[1] + 0.6 * shoulder_mid[1])
    head_top = (nose[0], max(0, nose[1] - 0.08))

    def pct(x: float, y: float) -> tuple:
        return (round(x * 100, 2), round(y * 100, 2))

    return [
        {"name": "head_top", "x": pct(*head_top)[0], "y": pct(*head_top)[1], "visibility": 2},
        {"name": "head_center", "x": pct(*nose)[0], "y": pct(*nose)[1], "visibility": 2},
        {"name": "chin", "x": pct(*mouth_mid)[0], "y": pct(*mouth_mid)[1], "visibility": 2},
        {"name": "neck", "x": pct(*neck)[0], "y": pct(*neck)[1], "visibility": 2},
        {"name": "chest_center", "x": pct(*shoulder_mid)[0], "y": pct(*shoulder_mid)[1], "visibility": 2},
        {"name": "spine_mid", "x": pct(*spine_mid)[0], "y": pct(*spine_mid)[1], "visibility": 2},
        {"name": "pelvis_center", "x": pct(*pelvis)[0], "y": pct(*pelvis)[1], "visibility": 2},
        {"name": "left_shoulder", "x": pct(*l_shoulder)[0], "y": pct(*l_shoulder)[1], "visibility": 2},
        {"name": "left_elbow", "x": pct(*L(MP.LEFT_ELBOW))[0], "y": pct(*L(MP.LEFT_ELBOW))[1], "visibility": 2},
        {"name": "left_wrist", "x": pct(*L(MP.LEFT_WRIST))[0], "y": pct(*L(MP.LEFT_WRIST))[1], "visibility": 2},
        {"name": "left_palm", "x": pct(*L(MP.LEFT_INDEX))[0], "y": pct(*L(MP.LEFT_INDEX))[1], "visibility": 2},
        {"name": "right_shoulder", "x": pct(*r_shoulder)[0], "y": pct(*r_shoulder)[1], "visibility": 2},
        {"name": "right_elbow", "x": pct(*L(MP.RIGHT_ELBOW))[0], "y": pct(*L(MP.RIGHT_ELBOW))[1], "visibility": 2},
        {"name": "right_wrist", "x": pct(*L(MP.RIGHT_WRIST))[0], "y": pct(*L(MP.RIGHT_WRIST))[1], "visibility": 2},
        {"name": "right_palm", "x": pct(*L(MP.RIGHT_INDEX))[0], "y": pct(*L(MP.RIGHT_INDEX))[1], "visibility": 2},
        {"name": "left_hip", "x": pct(*l_hip)[0], "y": pct(*l_hip)[1], "visibility": 2},
        {"name": "left_knee", "x": pct(*L(MP.LEFT_KNEE))[0], "y": pct(*L(MP.LEFT_KNEE))[1], "visibility": 2},
        {"name": "left_ankle", "x": pct(*L(MP.LEFT_ANKLE))[0], "y": pct(*L(MP.LEFT_ANKLE))[1], "visibility": 2},
        {"name": "left_toe", "x": pct(*L(MP.LEFT_FOOT_INDEX))[0], "y": pct(*L(MP.LEFT_FOOT_INDEX))[1], "visibility": 2},
        {"name": "right_hip", "x": pct(*r_hip)[0], "y": pct(*r_hip)[1], "visibility": 2},
        {"name": "right_knee", "x": pct(*L(MP.RIGHT_KNEE))[0], "y": pct(*L(MP.RIGHT_KNEE))[1], "visibility": 2},
        {"name": "right_ankle", "x": pct(*L(MP.RIGHT_ANKLE))[0], "y": pct(*L(MP.RIGHT_ANKLE))[1], "visibility": 2},
        {"name": "right_toe", "x": pct(*L(MP.RIGHT_FOOT_INDEX))[0], "y": pct(*L(MP.RIGHT_FOOT_INDEX))[1], "visibility": 2},
        {"name": "racket_grip", "x": 0, "y": 0, "visibility": 0},
        {"name": "racket_head", "x": 0, "y": 0, "visibility": 0},
    ]


def _empty_keypoints_list() -> List[Dict[str, Any]]:
    return [{"name": name, "x": 0, "y": 0, "visibility": 0} for name in KEYPOINT_NAMES]


# 模型优先级：full 精度更高，lite 更快；均下载到 D 盘 data/models/
_POSE_MODEL_URLS = [
    ("pose_landmarker_full.task", "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task"),
    ("pose_landmarker_heavy.task", "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"),
    ("pose_landmarker_lite.task", "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"),
]


def _ensure_pose_model() -> Optional[Path]:
    """确保 data/models 下存在姿态模型（优先 full/heavy 提升识别能力），缺失时下载到 D 盘。"""
    models_dir = Path(settings.DATA_DIR) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in _POSE_MODEL_URLS:
        path = models_dir / filename
        if path.exists():
            return path
        try:
            import urllib.request
            logger.info("正在下载姿态模型到 D 盘: %s <- %s", path, url)
            req = urllib.request.Request(url, headers={"User-Agent": "Badminton-Annotation/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                path.write_bytes(resp.read())
            if path.stat().st_size > 0:
                return path
        except Exception as e:
            logger.debug("下载 %s 失败，尝试下一档: %s", filename, e)
            continue
    logger.warning("所有姿态模型下载均失败，将使用单人检测回退")
    return None


def predict_keypoints_multi_from_image_path(image_path: Union[str, Path]) -> List[List[Dict[str, Any]]]:
    """
    对一张图片做姿态估计，支持多人。返回 persons: 每人一组 25 关键点（0–100%）。
    优先使用 full/heavy 模型（人体识别能力更强），缺失时再试 lite；均存于 D 盘 data/models/。
    若无 .task 模型则回退到单人 MediaPipe Pose（model_complexity=2 提升精度）。
    """
    try:
        import cv2
    except ImportError:
        logger.warning("pose_service: opencv not installed")
        return []

    path = Path(image_path)
    if not path.exists():
        logger.warning("pose_service: file not found %s", path)
        return []

    image = cv2.imread(str(path))
    if image is None:
        logger.warning("pose_service: failed to read image %s", path)
        return []

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    model_path = _ensure_pose_model()

    # 尝试多人 PoseLandmarker（Tasks API）
    if model_path:
        try:
            from mediapipe.tasks import python as mp_tasks
            from mediapipe.tasks.python import vision

            base_options = mp_tasks.BaseOptions(model_asset_path=str(model_path))
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                num_poses=6,
                min_pose_detection_confidence=0.4,
                min_pose_presence_confidence=0.4,
            )
            with vision.PoseLandmarker.create_from_options(options) as landmarker:
                mp_image = vision.ImageImage.create_from_array(rgb)
                result = landmarker.detect(mp_image)
            if result.pose_landmarks:
                out = []
                for person_landmarks in result.pose_landmarks:
                    # 每人可能是 .landmark 列表或直接可索引
                    lm = getattr(person_landmarks, "landmark", person_landmarks)
                    if hasattr(lm, "__iter__") and not isinstance(lm, (dict, str)):
                        lm = list(lm)
                    out.append(_landmarks_to_our_25(lm))
                return out
        except Exception as e:
            logger.warning("PoseLandmarker 多人检测失败，回退单人: %s", e)

    # 回退：单人 MediaPipe Pose
    try:
        import mediapipe as mp
        mp_pose = mp.solutions.pose
        with mp_pose.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.4) as pose:
            results = pose.process(rgb)
        if results.pose_landmarks:
            return [_landmarks_to_our_25(results.pose_landmarks.landmark)]
    except Exception as e:
        logger.warning("pose_service: single-person fallback failed %s", e)
    return []


def predict_keypoints_from_image_path(image_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """单人接口：返回第一人的 25 关键点，兼容原 API。"""
    persons = predict_keypoints_multi_from_image_path(image_path)
    if persons:
        return persons[0]
    return _empty_keypoints_list()
