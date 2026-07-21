"""Inter-annotator agreement for categorical labels and 2D keypoints."""

from collections import Counter, defaultdict
from itertools import combinations
from math import hypot
from typing import Any, Dict, Iterable, List, Tuple


def _cohen_kappa(pairs: List[Tuple[Any, Any]]) -> dict:
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if not pairs:
        return {"n": 0, "observed_agreement": None, "expected_agreement": None, "kappa": None}
    observed = sum(a == b for a, b in pairs) / len(pairs)
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    labels = set(left) | set(right)
    expected = sum(left[label] / len(pairs) * right[label] / len(pairs) for label in labels)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else (1.0 if observed == 1 else 0.0)
    return {"n": len(pairs), "observed_agreement": observed, "expected_agreement": expected, "kappa": kappa}


def _points(annotation) -> Dict[str, Tuple[float, float]]:
    result = {}
    for point in annotation.keypoints or []:
        if not isinstance(point, dict) or not point.get("name") or int(point.get("visibility", 0) or 0) <= 0:
            continue
        try:
            result[str(point["name"])] = (float(point["x"]), float(point["y"]))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def build_agreement_report(annotations: Iterable, pck_thresholds=(0.05, 0.10), minimum_items: int = 20) -> dict:
    annotations = list(annotations)
    grouped = defaultdict(list)
    for annotation in annotations:
        grouped[(annotation.frame_index, annotation.selected_player_id)].append(annotation)
    item_pairs = []
    for key, values in grouped.items():
        distinct = {annotation.annotator_id: annotation for annotation in values}
        item_pairs.extend((key, left, right) for left, right in combinations(distinct.values(), 2))
    categorical = {
        field: _cohen_kappa([(getattr(left, field), getattr(right, field)) for _, left, right in item_pairs])
        for field in ("action_type", "action_phase", "quality_rating", "is_contact_event")
    }
    distances = []
    per_joint = defaultdict(list)
    for _, left, right in item_pairs:
        left_points, right_points = _points(left), _points(right)
        normalizer = hypot(max(float(left.box_w or 0), float(right.box_w or 0)), max(float(left.box_h or 0), float(right.box_h or 0))) or hypot(100.0, 100.0)
        for name in left_points.keys() & right_points.keys():
            distance = hypot(left_points[name][0] - right_points[name][0], left_points[name][1] - right_points[name][1]) / normalizer
            distances.append(distance)
            per_joint[name].append(distance)
    keypoints = {
        "comparable_joints": len(distances),
        "mean_normalized_error": sum(distances) / len(distances) if distances else None,
        "pck": {str(t): sum(d <= t for d in distances) / len(distances) if distances else None for t in pck_thresholds},
        "per_joint_mean_error": {name: sum(values) / len(values) for name, values in sorted(per_joint.items())},
    }
    annotators = {annotation.annotator_id for annotation in annotations}
    comparable_items = len(item_pairs)
    return {
        "annotation_count": len(annotations), "annotator_count": len(annotators),
        "double_annotated_items": comparable_items, "categorical": categorical, "keypoints": keypoints,
        "readiness": {
            "has_at_least_two_annotators": len(annotators) >= 2,
            "minimum_double_annotated_items": comparable_items >= minimum_items,
            "ready": len(annotators) >= 2 and comparable_items >= minimum_items,
        },
    }
