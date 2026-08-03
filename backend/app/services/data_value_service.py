"""Layered, explicitly provisional data-value assessment.

The service keeps four concepts separate:
1) low-cost sample difficulty,
2) annotation/data quality risk,
3) high-cost model loss evidence,
4) cost-adjusted value hypothesis.

It never reports the heuristic value score as an observed training gain.  A future
training experiment may write ``observed_value_gain`` into selection components;
those observations are surfaced separately for calibration and validation.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from app.models.annotation import FrameAnnotation
from app.models.batch_frame import BatchFrame
from app.services.influence_lite_service import score_batch_frames
from app.services.teacher_surrogate_service import analyze_batch


VERSION = "data-value-v1"
EPSILON = 1e-9


def _unit(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _entropy(distribution: Any) -> float:
    if not isinstance(distribution, dict) or len(distribution) < 2:
        return 0.0
    values = [max(0.0, float(value or 0.0)) for value in distribution.values()]
    total = sum(values)
    if total <= EPSILON:
        return 0.0
    probabilities = [value / total for value in values]
    return -sum(p * math.log(max(p, EPSILON)) for p in probabilities) / math.log(len(probabilities))


def _cross_entropy(distribution: Any, label: Any) -> float | None:
    if not isinstance(distribution, dict) or label not in distribution:
        return None
    return -math.log(max(EPSILON, min(1.0, float(distribution[label] or 0.0))))


def _loss_to_unit(value: float | None) -> float | None:
    # Stable bounded transformation; preserves order without letting an apparent
    # label error dominate the whole batch.
    return None if value is None else 1.0 - math.exp(-max(0.0, value))


def build_data_value_report(db, batch) -> dict:
    frames = (
        db.query(BatchFrame)
        .filter(BatchFrame.task_batch_id == batch.id)
        .order_by(BatchFrame.frame_index)
        .all()
    )
    annotations = (
        db.query(FrameAnnotation)
        .filter(FrameAnnotation.task_batch_id == batch.id)
        .order_by(FrameAnnotation.frame_index, FrameAnnotation.id)
        .all()
    )
    priorities = {item["frame_index"]: item for item in score_batch_frames(db, batch)}
    teacher_report = analyze_batch(db, batch)
    teacher_items = {item["annotation_id"]: item for item in teacher_report.get("items", [])}

    action_counts = Counter(annotation.action_type for annotation in annotations if annotation.action_type)
    max_action_count = max(action_counts.values(), default=1)
    frame_map = {frame.frame_index: frame for frame in frames}
    observed_value_gains = []
    results = []

    for annotation in annotations:
        metadata = annotation.assist_metadata if isinstance(annotation.assist_metadata, dict) else {}
        student_distribution = metadata.get("student_distribution") or metadata.get("phase_probabilities")
        entropy = _entropy(student_distribution)
        supervised_loss = _cross_entropy(student_distribution, annotation.action_phase)
        low_cost_mode = "supervised_loss" if supervised_loss is not None else "unlabeled_difficulty"
        low_cost_difficulty = _loss_to_unit(supervised_loss) if supervised_loss is not None else entropy

        teacher_item = teacher_items.get(annotation.id, {})
        teacher_loss = metadata.get("teacher_loss")
        teacher_source = "none"
        if isinstance(teacher_loss, (int, float)):
            target_loss = max(0.0, float(teacher_loss))
            teacher_source = "observed_teacher_loss"
        else:
            estimated_distribution = teacher_item.get("estimated_teacher_distribution")
            target_loss = _cross_entropy(estimated_distribution, annotation.action_phase)
            if target_loss is not None:
                teacher_source = teacher_item.get("teacher_source", "uncalibrated_surrogate")
        target_difficulty = _loss_to_unit(target_loss)

        frame = frame_map.get(annotation.frame_index)
        novelty = _unit(frame.selection_score if frame else 0.0)
        redundancy = 1.0 - novelty
        rarity = 1.0 - action_counts.get(annotation.action_type, 0) / max_action_count if annotation.action_type else 0.5
        quality_risk = _unit(teacher_item.get("quality_risk"), 0.0)
        priority = priorities.get(annotation.frame_index, {})
        estimated_cost = max(10.0, float(priority.get("estimated_cost_seconds") or 45.0))

        difficulty = target_difficulty if target_difficulty is not None else low_cost_difficulty
        # This is a hypothesis score to prioritize experiments, not measured value.
        information_potential = (
            0.40 * _unit(difficulty, 0.5)
            + 0.35 * novelty
            + 0.25 * _unit(rarity, 0.5)
        )
        proxy_value = _unit(
            information_potential
            * (1.0 - 0.75 * quality_risk)
            / math.sqrt(estimated_cost / 45.0)
        )

        components = dict(frame.selection_components or {}) if frame else {}
        observed_gain = components.get("observed_value_gain")
        if isinstance(observed_gain, (int, float)):
            observed_value_gains.append(float(observed_gain))

        flags = list(teacher_item.get("flags") or [])
        if quality_risk >= 0.55:
            decision = "review"
            decision_reason = "质量风险较高，先复核而非直接进入训练"
        elif redundancy >= 0.85 and entropy <= 0.45:
            decision = "defer"
            decision_reason = "信息增量较低，可降采样或延后处理"
        elif proxy_value >= 0.50:
            decision = "prioritize"
            decision_reason = "价值假设较高，建议进入下一轮训练验证"
        elif teacher_source in {"none", "uncalibrated_surrogate"} and entropy >= 0.65:
            decision = "calibrate"
            decision_reason = "代理不确定且尚未校准，适合抽样运行目标模型"
        else:
            decision = "regular"
            decision_reason = "普通候选，保留但不优先"

        evidence_level = (
            "observed_gain"
            if isinstance(observed_gain, (int, float))
            else "teacher_observed"
            if teacher_source.startswith("observed_")
            else "calibrated_proxy"
            if teacher_source == "calibrated_surrogate"
            else "exploratory_proxy"
        )
        results.append({
            "annotation_id": annotation.id,
            "frame_index": annotation.frame_index,
            "selected_player_id": annotation.selected_player_id,
            "action_type": annotation.action_type,
            "action_phase": annotation.action_phase,
            "low_cost": {
                "mode": low_cost_mode,
                "loss": round(supervised_loss, 4) if supervised_loss is not None else None,
                "entropy": round(entropy, 4),
                "difficulty": round(_unit(low_cost_difficulty), 4),
            },
            "target_model": {
                "loss": round(target_loss, 4) if target_loss is not None else None,
                "difficulty": round(target_difficulty, 4) if target_difficulty is not None else None,
                "source": teacher_source,
            },
            "quality_risk": round(quality_risk, 4),
            "information_potential": round(information_potential, 4),
            "novelty": round(novelty, 4),
            "redundancy": round(redundancy, 4),
            "class_rarity": round(_unit(rarity, 0.5), 4),
            "estimated_cost_seconds": round(estimated_cost, 1),
            "proxy_value_per_cost": round(proxy_value, 4),
            "observed_value_gain": round(float(observed_gain), 6) if isinstance(observed_gain, (int, float)) else None,
            "evidence_level": evidence_level,
            "decision": decision,
            "decision_reason": decision_reason,
            "flags": flags,
        })

    decision_counts = Counter(item["decision"] for item in results)
    proxy_values = [item["proxy_value_per_cost"] for item in results]
    quality_risks = [item["quality_risk"] for item in results]
    observed_teacher = sum(
        item["target_model"]["source"].startswith("observed_") for item in results
    )
    return {
        "version": VERSION,
        "task_batch_id": batch.id,
        "evidence_status": (
            "validated_observations"
            if observed_value_gains
            else "calibrated_proxy"
            if teacher_report.get("status") == "calibrated"
            else "exploratory_proxy"
        ),
        "interpretation": (
            "当前分数用于安排复核和训练实验，不代表已观测到的模型性能增益。"
            if not observed_value_gains
            else
            "部分数据已有训练增益观测；代理分数与真实增益仍需按比赛分组验证。"
        ),
        "definitions": {
            "difficulty": "当前模型对样本的拟合难度，不等于数据价值",
            "quality_risk": "错标、时序异常或低质量风险；高风险先复核",
            "proxy_value_per_cost": "难度、新颖度、稀缺度和成本形成的待验证价值假设",
            "observed_value_gain": "受控增量训练实验得到的目标模型验证性能变化",
        },
        "calibration": {
            "teacher_status": teacher_report.get("status"),
            "paired_teacher_samples": teacher_report.get("calibration", {}).get("paired_samples", 0),
            "observed_teacher_evaluations": observed_teacher,
            "observed_training_gains": len(observed_value_gains),
        },
        "summary": {
            "total_frames": len(frames),
            "total_annotations": len(annotations),
            "analyzed": len(results),
            "coverage": round(len(results) / max(1, len(annotations)), 4),
            "mean_proxy_value_per_cost": round(mean(proxy_values), 4) if proxy_values else 0.0,
            "mean_quality_risk": round(mean(quality_risks), 4) if quality_risks else 0.0,
            "decision_counts": dict(decision_counts),
            "mean_observed_value_gain": round(mean(observed_value_gains), 6) if observed_value_gains else None,
        },
        "items": sorted(results, key=lambda item: (
            item["decision"] != "review",
            -item["proxy_value_per_cost"],
        )),
    }
