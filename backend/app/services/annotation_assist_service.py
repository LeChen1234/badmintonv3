"""Explainable pose assistance; never infers a badminton stroke from one frame.

The output is designed for human-in-the-loop annotation: a probability
distribution, normalized entropy, a biomechanics-inspired energy functional,
and explicit reasons. It suggests phase/quality only when evidence is strong.
"""

import math
from typing import Any, Dict, Iterable, Optional, Tuple


def _point(points: Dict[str, dict], name: str) -> Optional[Tuple[float, float]]:
    value = points.get(name)
    if not value or int(value.get("visibility", 0)) <= 0:
        return None
    x, y = value.get("x"), value.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return float(x), float(y)


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _angle(a, b, c) -> Optional[float]:
    if a is None or b is None or c is None:
        return None
    u, v = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
    denominator = math.hypot(*u) * math.hypot(*v)
    if denominator <= 1e-9:
        return None
    cosine = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / denominator))
    return math.degrees(math.acos(cosine))


def _softmax(logits: Dict[str, float]) -> Dict[str, float]:
    maximum = max(logits.values())
    values = {key: math.exp(value - maximum) for key, value in logits.items()}
    total = sum(values.values())
    return {key: value / total for key, value in values.items()}


def _entropy(probabilities: Iterable[float]) -> float:
    values = list(probabilities)
    if len(values) < 2:
        return 0.0
    value = -sum(p * math.log(max(p, 1e-12)) for p in values)
    return value / math.log(len(values))


def analyze_pose(keypoints: list[dict]) -> Dict[str, Any]:
    points = {point.get("name"): point for point in keypoints if point.get("name")}
    body_names = [name for name in points if not name.startswith("racket_")]
    visible = sum(1 for name in body_names if _point(points, name) is not None)
    completeness = visible / max(1, len(body_names))

    ls, rs = _point(points, "left_shoulder"), _point(points, "right_shoulder")
    lh, rh = _point(points, "left_hip"), _point(points, "right_hip")
    shoulders = None if ls is None or rs is None else ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
    hips = None if lh is None or rh is None else ((lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2)
    scale = _distance(shoulders, hips) if shoulders and hips else 0.0
    if scale <= 1e-6:
        return {
            "algorithm_version": "info-functional-v1",
            "confidence": 0.0, "uncertainty": 1.0, "review_priority": 1.0,
            "suggested_phase": None, "suggested_quality": None,
            "phase_probabilities": {}, "features": {"completeness": completeness},
            "reasons": ["躯干关键点不足，无法形成稳定的人体尺度"],
        }

    arms = []
    for side in ("left", "right"):
        shoulder, elbow, wrist = (_point(points, f"{side}_{part}") for part in ("shoulder", "elbow", "wrist"))
        angle = _angle(shoulder, elbow, wrist)
        if shoulder and wrist and angle is not None:
            arms.append((side, (shoulder[1] - wrist[1]) / scale, angle / 180.0))
    dominant = max(arms, key=lambda value: value[1] + 0.3 * value[2]) if arms else ("unknown", 0.0, 0.0)
    side, wrist_height, arm_extension = dominant

    left_knee = _angle(lh, _point(points, "left_knee"), _point(points, "left_ankle"))
    right_knee = _angle(rh, _point(points, "right_knee"), _point(points, "right_ankle"))
    knee_flexion = 0.0
    available_knees = [value for value in (left_knee, right_knee) if value is not None]
    if available_knees:
        knee_flexion = sum((180.0 - value) / 180.0 for value in available_knees) / len(available_knees)
    shoulder_tilt = abs(ls[1] - rs[1]) / scale if ls and rs else 1.0

    logits = {
        "preparation": 0.8 - abs(wrist_height) - 0.4 * arm_extension,
        "backswing": 0.3 + max(0.0, wrist_height) + (1.0 - arm_extension),
        "contact": 0.2 + 1.8 * max(0.0, wrist_height) + 1.4 * arm_extension,
        "follow_through": 0.2 + 0.9 * arm_extension + max(0.0, -wrist_height),
        "recovery": 0.4 + (1.0 - min(1.0, abs(wrist_height))) + 0.3 * knee_flexion,
    }
    probabilities = _softmax(logits)
    phase, phase_probability = max(probabilities.items(), key=lambda item: item[1])
    uncertainty = _entropy(probabilities.values())
    confidence = max(0.0, min(1.0, completeness * phase_probability * (1.0 - 0.35 * uncertainty)))

    # E[x] = missing-data penalty + posture asymmetry + insufficient kinetic-chain evidence.
    quality_energy = min(1.0, 0.45 * (1.0 - completeness) + 0.30 * min(1.0, shoulder_tilt) + 0.25 * (1.0 - arm_extension))
    suggested_quality = None
    if confidence >= 0.55:
        suggested_quality = "needs_correction" if quality_energy >= 0.48 else "acceptable"
    suggested_phase = phase if confidence >= 0.42 else None
    review_priority = min(1.0, 0.55 * uncertainty + 0.30 * (1.0 - completeness) + 0.15 * quality_energy)

    reasons = [f"{side}侧手臂为主要观测链", f"阶段分布熵={uncertainty:.2f}"]
    if completeness < 0.8:
        reasons.append("关键点缺失较多，应优先人工核验")
    if shoulder_tilt > 0.25:
        reasons.append("肩线倾斜幅度较大，姿态完整度评分降低")
    if phase_probability < 0.45:
        reasons.append("阶段候选接近，算法不应自动定标")

    return {
        "algorithm_version": "info-functional-v1",
        "confidence": round(confidence, 4),
        "uncertainty": round(uncertainty, 4),
        "review_priority": round(review_priority, 4),
        "suggested_phase": suggested_phase,
        "suggested_quality": suggested_quality,
        "phase_probabilities": {key: round(value, 4) for key, value in probabilities.items()},
        "features": {
            "completeness": round(completeness, 4), "dominant_side": side,
            "wrist_height": round(wrist_height, 4), "arm_extension": round(arm_extension, 4),
            "knee_flexion": round(knee_flexion, 4), "shoulder_tilt": round(shoulder_tilt, 4),
            "quality_energy": round(quality_energy, 4),
        },
        "reasons": reasons,
    }
