"""Cost-aware feedback and pre-registered stopping for active annotation."""

import math
from typing import Dict, Optional, Sequence, Tuple

from app.services.research_release_service import load_research_protocol


COMPONENTS = ("motion", "entropy", "spectral", "calculus")


def current_project_weights(db, project_id: int) -> Dict[str, float]:
    from app.models.active_learning_round import ActiveLearningRound
    latest = db.query(ActiveLearningRound).filter(
        ActiveLearningRound.project_id == project_id
    ).order_by(ActiveLearningRound.round_index.desc()).first()
    if latest:
        return dict(latest.recommended_weights)
    return dict(load_research_protocol()["active_learning"]["initial_component_weights"])


def _normalize_weights(values: Dict[str, float], floor: float) -> Dict[str, float]:
    safe = {name: max(floor, float(values.get(name, 0.0))) for name in COMPONENTS}
    total = sum(safe.values())
    return {name: value / total for name, value in safe.items()}


def recommend_weights(previous: Optional[dict], component_gains: Dict[str, float], config: dict) -> Dict[str, float]:
    initial = _normalize_weights(config["initial_component_weights"], 0.0)
    prior = _normalize_weights(previous or initial, 0.0)
    positive = {name: max(0.0, float(component_gains.get(name, 0.0))) for name in COMPONENTS}
    if sum(positive.values()) <= 1e-12:
        return prior
    evidence = _normalize_weights(positive, float(config.get("minimum_component_weight", 0.05)))
    rate = max(0.0, min(1.0, float(config.get("weight_update_rate", 0.3))))
    return _normalize_weights({name: (1 - rate) * prior[name] + rate * evidence[name] for name in COMPONENTS}, 0.0)


def marginal_utility(previous_metrics: Optional[dict], metrics: dict, annotation_hours: float, config: dict) -> dict:
    if not previous_metrics:
        return {"delta_macro_f1": None, "delta_std": None, "lower95": None, "upper95": None, "gain_per_hour": None, "upper_gain_per_hour": None}
    current_mean = float(metrics["macro_f1_mean"])
    previous_mean = float(previous_metrics["macro_f1_mean"])
    delta = current_mean - previous_mean
    current_se = float(metrics.get("macro_f1_std", 0.0)) / math.sqrt(max(1, int(metrics.get("repeat_count", 1))))
    previous_se = float(previous_metrics.get("macro_f1_std", 0.0)) / math.sqrt(max(1, int(previous_metrics.get("repeat_count", 1))))
    delta_std = math.sqrt(current_se ** 2 + previous_se ** 2)
    z = float(config.get("confidence_z", 1.96))
    return {
        "delta_macro_f1": delta,
        "delta_std": delta_std,
        "lower95": delta - z * delta_std,
        "upper95": delta + z * delta_std,
        "gain_per_hour": delta / annotation_hours,
        "upper_gain_per_hour": (delta + z * delta_std) / annotation_hours,
    }


def evaluate_round(
    prior_rounds: Sequence,
    metrics: dict,
    annotation_hours: float,
    component_gains: Dict[str, float],
) -> Tuple[dict, Dict[str, float], bool, dict]:
    config = load_research_protocol()["active_learning"]
    previous = prior_rounds[-1] if prior_rounds else None
    utility = marginal_utility(previous.metrics if previous else None, metrics, annotation_hours, config)
    weights = recommend_weights(previous.recommended_weights if previous else None, component_gains, config)
    recent_upper = [
        round_.marginal_utility.get("upper_gain_per_hour")
        for round_ in prior_rounds
        if round_.marginal_utility.get("upper_gain_per_hour") is not None
    ]
    if utility["upper_gain_per_hour"] is not None:
        recent_upper.append(utility["upper_gain_per_hour"])
    patience = int(config["stopping_patience"])
    threshold = float(config["minimum_macro_f1_gain_per_hour"])
    enough_rounds = len(prior_rounds) + 1 >= int(config["minimum_rounds"])
    stop = enough_rounds and len(recent_upper) >= patience and all(value < threshold for value in recent_upper[-patience:])
    decision = {
        "stop_recommended": stop,
        "reason": (
            f"Last {patience} rounds' 95% upper gain per hour is below {threshold}"
            if stop else "Continue: stopping evidence is not yet sufficient"
        ),
        "threshold_gain_per_hour": threshold,
        "patience": patience,
    }
    return utility, weights, stop, decision
