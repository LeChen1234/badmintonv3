"""Conservative deterministic fallback for Label Studio.

A single template frame cannot identify stroke type, so the fallback returns
``other`` instead of fabricating a class. Real pose assistance is served by the
FastAPI application with entropy/confidence diagnostics.
"""

from typing import Dict, List

ACTION_TYPES = [
    ("smash", 0.12),
    ("clear", 0.12),
    ("drop_shot", 0.08),
    ("net_shot", 0.08),
    ("drive", 0.08),
    ("lift", 0.06),
    ("push", 0.06),
    ("block", 0.05),
    ("backhand_clear", 0.05),
    ("backhand_drop", 0.04),
    ("serve_forehand", 0.06),
    ("serve_backhand", 0.04),
    ("footwork_lunge", 0.03),
    ("footwork_jump", 0.03),
    ("footwork_shuffle", 0.03),
    ("ready_stance", 0.03),
    ("recovery", 0.03),
    ("other", 0.01),
]

ACTION_PHASES = [
    "preparation", "backswing", "forward_swing",
    "contact", "follow_through", "recovery_phase",
]

QUALITY_RATINGS = ["standard", "acceptable", "needs_correction"]
QUALITY_WEIGHTS = [0.4, 0.4, 0.2]


def recognize_action() -> List[Dict]:
    """Return a deterministic, explicitly uncertain baseline prediction.

    Returns list of dicts in Label Studio Choices result format.
    """
    action = "other"
    phase = "preparation"
    quality = "acceptable"

    return [
        {
            "from_name": "action_type",
            "to_name": "image",
            "type": "choices",
            "value": {"choices": [action]},
        },
        {
            "from_name": "action_phase",
            "to_name": "image",
            "type": "choices",
            "value": {"choices": [phase]},
        },
        {
            "from_name": "quality_rating",
            "to_name": "image",
            "type": "choices",
            "value": {"choices": [quality]},
        },
    ]
