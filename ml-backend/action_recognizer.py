"""Mock action recognizer for badminton action classification.

Returns random but weighted action predictions.
Replace with real classifier for production use.
"""

import random
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
    """Generate mock action classification predictions.

    Returns list of dicts in Label Studio Choices result format.
    """
    actions, weights = zip(*ACTION_TYPES)
    action = random.choices(actions, weights=weights, k=1)[0]
    phase = random.choice(ACTION_PHASES)
    quality = random.choices(QUALITY_RATINGS, weights=QUALITY_WEIGHTS, k=1)[0]

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
