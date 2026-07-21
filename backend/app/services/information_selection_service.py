"""Information-theoretic temporal scoring for annotation frame selection.

The score is intentionally model-independent and decomposable for ablation:
motion magnitude (data term), local Shannon entropy (information term), DCT
high-frequency energy (transform term), and finite-difference acceleration /
jerk (calculus term). All components are normalized to [0, 1].
"""

import math
from typing import Dict, List, Sequence


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(float(v) for v in values)
    pos = (len(xs) - 1) * max(0.0, min(100.0, q)) / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] if lo == hi else xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def _robust_unit(values: Sequence[float]) -> List[float]:
    """Robust [0,1] scaling; P5/P95 limits prevent one spike dominating."""
    if not values:
        return []
    low, high = _percentile(values, 5), _percentile(values, 95)
    if high - low <= 1e-12:
        return [0.0 for _ in values]
    return [max(0.0, min(1.0, (float(v) - low) / (high - low))) for v in values]


def _difference(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    return [0.0] + [float(values[i]) - float(values[i - 1]) for i in range(1, len(values))]


def _window(values: Sequence[float], center: int, radius: int) -> List[float]:
    return list(values[max(0, center - radius): min(len(values), center + radius + 1)])


def _normalized_entropy(values: Sequence[float], bins: int = 6) -> float:
    if len(values) < 2:
        return 0.0
    low, high = min(values), max(values)
    if high - low <= 1e-12:
        return 0.0
    counts = [0] * bins
    for value in values:
        idx = min(bins - 1, int((value - low) / (high - low) * bins))
        counts[idx] += 1
    entropy = 0.0
    for count in counts:
        if count:
            probability = count / len(values)
            entropy -= probability * math.log(probability)
    return entropy / math.log(min(bins, len(values)))


def _dct_high_frequency_ratio(values: Sequence[float]) -> float:
    """Energy ratio of DCT-II coefficients k>=2, excluding the DC term."""
    n = len(values)
    if n < 4:
        return 0.0
    coefficients = []
    for k in range(1, n):
        coefficient = sum(
            float(value) * math.cos(math.pi * (index + 0.5) * k / n)
            for index, value in enumerate(values)
        )
        coefficients.append(coefficient)
    total = sum(value * value for value in coefficients)
    if total <= 1e-12:
        return 0.0
    return min(1.0, sum(value * value for value in coefficients[1:]) / total)


def score_motion_sequence(
    motion: Sequence[float],
    *,
    window_radius: int = 4,
    weights: Dict[str, float] | None = None,
) -> List[Dict[str, float]]:
    """Evaluate the frame-selection functional and expose every component."""
    if not motion:
        return []
    weights = weights or {"motion": 0.40, "entropy": 0.25, "spectral": 0.20, "calculus": 0.15}
    total_weight = sum(max(0.0, value) for value in weights.values()) or 1.0
    velocity = list(float(v) for v in motion)
    acceleration = _difference(velocity)
    jerk = _difference(acceleration)
    motion_component = _robust_unit(velocity)
    calculus_component = _robust_unit([
        abs(acceleration[i]) + 0.5 * abs(jerk[i]) for i in range(len(velocity))
    ])
    entropy_component = [
        _normalized_entropy(_window(velocity, i, window_radius)) for i in range(len(velocity))
    ]
    spectral_component = [
        _dct_high_frequency_ratio(_window(velocity, i, window_radius)) for i in range(len(velocity))
    ]

    result = []
    for i in range(len(velocity)):
        components = {
            "motion": motion_component[i],
            "entropy": entropy_component[i],
            "spectral": spectral_component[i],
            "calculus": calculus_component[i],
        }
        score = sum(weights.get(name, 0.0) * value for name, value in components.items()) / total_weight
        result.append({
            "score": max(0.0, min(1.0, score)),
            "velocity": velocity[i],
            "acceleration": acceleration[i],
            "jerk": jerk[i],
            **components,
        })
    return result


def diverse_indices(scores: Sequence[float], threshold: float, min_gap: int = 2) -> List[int]:
    """Greedy temporal non-maximum suppression to reduce near-duplicate frames."""
    candidates = sorted(
        (i for i, score in enumerate(scores) if score >= threshold),
        key=lambda i: (-scores[i], i),
    )
    selected: List[int] = []
    for index in candidates:
        if all(abs(index - existing) > min_gap for existing in selected):
            selected.append(index)
    return sorted(selected)
