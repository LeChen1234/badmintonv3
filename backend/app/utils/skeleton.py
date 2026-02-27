"""Skeleton normalization utilities.

Provides centering, scaling, and rotation normalization
for skeleton keypoint data.
"""

import math
from typing import Dict, List, Optional, Tuple

SKELETON_CONNECTIONS = [
    ("head_top", "head_center"), ("head_center", "chin"), ("chin", "neck"),
    ("neck", "chest_center"), ("chest_center", "spine_mid"), ("spine_mid", "pelvis_center"),
    ("neck", "left_shoulder"), ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"), ("left_wrist", "left_palm"),
    ("neck", "right_shoulder"), ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"), ("right_wrist", "right_palm"),
    ("pelvis_center", "left_hip"), ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"), ("left_ankle", "left_toe"),
    ("pelvis_center", "right_hip"), ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"), ("right_ankle", "right_toe"),
    ("right_wrist", "racket_grip"), ("racket_grip", "racket_head"),
]


def normalize_skeleton(
    keypoints: Dict[str, Tuple[float, float]],
    center_joint: str = "pelvis_center",
    scale_reference: Optional[Tuple[str, str]] = ("neck", "pelvis_center"),
) -> Dict[str, Tuple[float, float]]:
    """Normalize keypoints: center on a joint and scale by torso length."""
    if center_joint not in keypoints:
        return keypoints

    cx, cy = keypoints[center_joint]

    centered = {k: (x - cx, y - cy) for k, (x, y) in keypoints.items()}

    scale = 1.0
    if scale_reference:
        j1, j2 = scale_reference
        if j1 in centered and j2 in centered:
            dx = centered[j1][0] - centered[j2][0]
            dy = centered[j1][1] - centered[j2][1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 1e-6:
                scale = 1.0 / dist

    normalized = {k: (x * scale, y * scale) for k, (x, y) in centered.items()}
    return normalized


def rotate_skeleton(
    keypoints: Dict[str, Tuple[float, float]],
    angle_degrees: float,
) -> Dict[str, Tuple[float, float]]:
    """Rotate all keypoints around origin by given angle."""
    rad = math.radians(angle_degrees)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    return {
        k: (x * cos_a - y * sin_a, x * sin_a + y * cos_a)
        for k, (x, y) in keypoints.items()
    }


def flip_skeleton_horizontal(
    keypoints: Dict[str, Tuple[float, float]],
) -> Dict[str, Tuple[float, float]]:
    """Mirror skeleton horizontally, swapping left/right joints."""
    flipped = {}
    for k, (x, y) in keypoints.items():
        new_key = k
        if "left_" in k:
            new_key = k.replace("left_", "right_")
        elif "right_" in k:
            new_key = k.replace("right_", "left_")
        flipped[new_key] = (-x, y)
    return flipped
