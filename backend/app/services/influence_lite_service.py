"""Model-aware, cost-aware frame prioritization with an upgrade path to true gradients.

The proxy is deliberately auditable: every component is returned separately.  When a
future training job writes ``gradient_influence`` into a frame's selection components,
the same API automatically blends it into the priority without changing stored labels.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import median
from typing import Any

from app.models.annotation import FrameAnnotation
from app.models.annotation_revision import AnnotationRevision
from app.models.batch_frame import BatchFrame
from app.services.research_release_service import load_research_protocol


VERSION = "influence-lite-v1"


def _unit(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def score_batch_frames(db, batch) -> list[dict]:
    frames = db.query(BatchFrame).filter(BatchFrame.task_batch_id == batch.id).order_by(BatchFrame.frame_index).all()
    annotations = db.query(FrameAnnotation).filter(FrameAnnotation.task_batch_id == batch.id).all()
    by_frame: dict[int, list] = defaultdict(list)
    for annotation in annotations:
        by_frame[annotation.frame_index].append(annotation)

    annotation_ids = [annotation.id for annotation in annotations]
    revision_counts: Counter[int] = Counter()
    if annotation_ids:
        revision_counts.update(
            annotation_id
            for (annotation_id,) in db.query(AnnotationRevision.annotation_id)
            .filter(AnnotationRevision.annotation_id.in_(annotation_ids)).all()
        )

    action_counts = Counter(annotation.action_type for annotation in annotations if annotation.action_type)
    max_action_count = max(action_counts.values(), default=1)
    completed = sum(bool(by_frame.get(frame.frame_index)) or bool(frame.is_rejected) for frame in frames)
    completion_ratio = completed / max(1, len(frames))
    config = load_research_protocol()["active_learning"].get("influence_lite", {})
    phase = "cold_start" if completion_ratio < float(config.get("cold_start_until_completion_ratio", 0.2)) else "model_guided"

    observed_durations = [
        annotation.annotation_duration_ms / 1000
        for annotation in annotations
        if annotation.annotation_duration_ms and 2_000 <= annotation.annotation_duration_ms <= 600_000
    ]
    baseline_cost = median(observed_durations) if observed_durations else 45.0
    expected_people = 4 if batch.match_format == "doubles" else 2

    results = []
    for frame in frames:
        records = by_frame.get(frame.frame_index, [])
        components = dict(frame.selection_components or {})
        temporal_novelty = _unit(frame.selection_score)

        uncertainties = []
        for record in records:
            assist = record.assist_metadata if isinstance(record.assist_metadata, dict) else {}
            uncertainties.append(_unit(assist.get("review_priority"), 0.5))
        uncertainty = max(uncertainties, default=0.5)

        if records:
            rarities = [1.0 - action_counts.get(record.action_type, 0) / max_action_count for record in records if record.action_type]
            class_rarity = max(rarities, default=0.5)
            correction_events = sum(revision_counts.get(record.id, 0) for record in records)
            correction_signal = min(1.0, correction_events / max(1, 2 * len(records)))
        else:
            class_rarity = 0.5
            correction_signal = 0.0

        if phase == "cold_start":
            weights = dict(config.get("cold_start_weights") or {"temporal_novelty": 0.50, "uncertainty": 0.15, "class_rarity": 0.25, "correction": 0.10})
        else:
            weights = dict(config.get("model_guided_weights") or {"temporal_novelty": 0.25, "uncertainty": 0.35, "class_rarity": 0.25, "correction": 0.15})
        proxy_influence = (
            weights["temporal_novelty"] * temporal_novelty
            + weights["uncertainty"] * uncertainty
            + weights["class_rarity"] * class_rarity
            + weights["correction"] * correction_signal
        )

        gradient_value = components.get("gradient_influence")
        has_gradient = isinstance(gradient_value, (int, float))
        gradient_weight = _unit(config.get("gradient_blend_weight"), 0.5)
        influence = (1 - gradient_weight) * proxy_influence + gradient_weight * _unit(gradient_value) if has_gradient else proxy_influence

        actual_seconds = [
            record.annotation_duration_ms / 1000
            for record in records
            if record.annotation_duration_ms and 2_000 <= record.annotation_duration_ms <= 600_000
        ]
        estimated_cost = median(actual_seconds) if actual_seconds else baseline_cost * (expected_people / 2) * (0.8 + 0.4 * uncertainty)
        priority = influence / math.sqrt(max(10.0, estimated_cost) / 45.0)
        priority = _unit(priority)

        reasons = []
        if frame.is_rejected:
            influence, priority = -1.0, 0.0
            reasons.append(f"已跳过：{frame.rejection_reason or '无标注价值'}")
        else:
            ranked = sorted(
                ((temporal_novelty, "时序变化/新颖性较高"), (uncertainty, "模型或人工复核不确定度较高"),
                 (class_rarity, "可能补充稀缺动作分布"), (correction_signal, "同类样本人工修正较多")),
                reverse=True,
            )
            reasons.extend(reason for value, reason in ranked[:2] if value >= 0.45)
            if has_gradient:
                reasons.insert(0, "已融合训练梯度影响")
            if not reasons:
                reasons.append("普通候选，信息增益有限")

        results.append({
            "frame_index": frame.frame_index,
            "timestamp_ms": frame.timestamp_ms,
            "priority": round(priority, 4),
            "influence": round(influence, 4),
            "estimated_cost_seconds": round(estimated_cost, 1),
            "is_annotated": bool(records),
            "is_rejected": bool(frame.is_rejected),
            "phase": phase,
            "mode": "gradient_blend" if has_gradient else "proxy",
            "version": VERSION,
            "components": {
                "temporal_novelty": round(temporal_novelty, 4),
                "uncertainty": round(uncertainty, 4),
                "class_rarity": round(class_rarity, 4),
                "correction_signal": round(correction_signal, 4),
                "gradient_influence": round(_unit(gradient_value), 4) if has_gradient else None,
            },
            "weights": weights,
            "reasons": reasons,
        })
    return results
