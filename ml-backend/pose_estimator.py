"""Mock pose estimator for badminton skeleton keypoints.

Returns anatomically plausible random keypoint coordinates.
Replace with HRNet/ViTPose integration for production use.
"""

import random
from typing import Dict, List, Tuple

KEYPOINT_NAMES = [
    "head_top", "head_center", "chin",
    "neck", "chest_center", "spine_mid", "pelvis_center",
    "left_shoulder", "left_elbow", "left_wrist", "left_palm",
    "right_shoulder", "right_elbow", "right_wrist", "right_palm",
    "left_hip", "left_knee", "left_ankle", "left_toe",
    "right_hip", "right_knee", "right_ankle", "right_toe",
    "racket_grip", "racket_head",
]

SKELETON_TEMPLATE: Dict[str, Tuple[float, float]] = {
    "head_top":       (50.0, 8.0),
    "head_center":    (50.0, 12.0),
    "chin":           (50.0, 16.0),
    "neck":           (50.0, 20.0),
    "chest_center":   (50.0, 30.0),
    "spine_mid":      (50.0, 40.0),
    "pelvis_center":  (50.0, 50.0),
    "left_shoulder":  (42.0, 22.0),
    "left_elbow":     (36.0, 34.0),
    "left_wrist":     (32.0, 44.0),
    "left_palm":      (30.0, 47.0),
    "right_shoulder": (58.0, 22.0),
    "right_elbow":    (64.0, 34.0),
    "right_wrist":    (68.0, 44.0),
    "right_palm":     (70.0, 47.0),
    "left_hip":       (45.0, 52.0),
    "left_knee":      (43.0, 66.0),
    "left_ankle":     (42.0, 80.0),
    "left_toe":       (40.0, 84.0),
    "right_hip":      (55.0, 52.0),
    "right_knee":     (57.0, 66.0),
    "right_ankle":    (58.0, 80.0),
    "right_toe":      (60.0, 84.0),
    "racket_grip":    (70.0, 47.0),
    "racket_head":    (78.0, 38.0),
}


def estimate_keypoints(
    image_width: int = 640,
    image_height: int = 480,
    jitter: float = 3.0,
) -> List[Dict]:
    """Generate mock keypoint predictions with anatomical jitter.

    Returns list of dicts in Label Studio KeyPointLabels result format.
    Coordinates are in percentage (0-100) of image dimensions.
    """
    results = []
    for name in KEYPOINT_NAMES:
        base_x, base_y = SKELETON_TEMPLATE[name]
        x = max(0.0, min(100.0, base_x + random.gauss(0, jitter)))
        y = max(0.0, min(100.0, base_y + random.gauss(0, jitter)))

        results.append({
            "original_width": image_width,
            "original_height": image_height,
            "image_rotation": 0,
            "value": {
                "x": round(x, 2),
                "y": round(y, 2),
                "width": 1.0,
                "keypointlabels": [name],
            },
        })
    return results
