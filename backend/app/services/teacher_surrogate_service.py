"""Estimate teacher-model distributions from small-model outputs for dataset QA.

This is intentionally a surrogate, not a claim that the teacher was executed.  When
paired teacher distributions are present in ``assist_metadata.teacher_distribution``,
the service learns a smoothed class-transition matrix and reports calibration status.
Without pairs it uses an identity mapping with mild empirical-prior shrinkage.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from app.models.annotation import FrameAnnotation
from app.models.batch_frame import BatchFrame


VERSION = "teacher-surrogate-v1"
EPSILON = 1e-9


def _distribution(value: Any, classes: list[str]) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    clean = {name: max(0.0, float(value.get(name, 0.0) or 0.0)) for name in classes}
    total = sum(clean.values())
    return {name: score / total for name, score in clean.items()} if total > EPSILON else None


def _entropy(distribution: dict[str, float]) -> float:
    if len(distribution) < 2:
        return 0.0
    return -sum(p * math.log(max(p, EPSILON)) for p in distribution.values()) / math.log(len(distribution))


def _js_divergence(left: dict[str, float], right: dict[str, float]) -> float:
    midpoint = {name: (left[name] + right[name]) / 2 for name in left}

    def kl(source, target):
        return sum(p * math.log(max(p, EPSILON) / max(target[name], EPSILON)) for name, p in source.items())

    return min(1.0, (kl(left, midpoint) + kl(right, midpoint)) / (2 * math.log(2)))


def _learn_transition(pairs: list[tuple[dict[str, float], dict[str, float]]], classes: list[str]) -> dict[str, dict[str, float]]:
    # Dirichlet smoothing keeps the map stable with very few calibration examples.
    matrix = {source: {target: (1.0 if source == target else 0.0) for target in classes} for source in classes}
    for student, teacher in pairs:
        for source in classes:
            for target in classes:
                matrix[source][target] += student[source] * teacher[target]
    for source in classes:
        total = sum(matrix[source].values())
        matrix[source] = {target: value / total for target, value in matrix[source].items()}
    return matrix


def _project(student: dict[str, float], matrix: dict[str, dict[str, float]], prior: dict[str, float], calibrated: bool) -> dict[str, float]:
    projected = {
        target: sum(student[source] * matrix[source][target] for source in student)
        for target in student
    }
    # In uncalibrated mode, only use a small prior shrinkage and avoid fabricating a
    # strong teacher correction unsupported by paired observations.
    prior_weight = 0.0 if calibrated else 0.12
    result = {name: (1 - prior_weight) * projected[name] + prior_weight * prior[name] for name in student}
    total = sum(result.values())
    return {name: value / total for name, value in result.items()}


def analyze_batch(db, batch) -> dict:
    annotations = (
        db.query(FrameAnnotation)
        .filter(FrameAnnotation.task_batch_id == batch.id)
        .order_by(FrameAnnotation.frame_index, FrameAnnotation.id)
        .all()
    )
    frames = {
        frame.frame_index: frame
        for frame in db.query(BatchFrame).filter(BatchFrame.task_batch_id == batch.id).all()
    }

    raw_distributions = []
    labels = Counter(annotation.action_phase for annotation in annotations if annotation.action_phase)
    for annotation in annotations:
        metadata = annotation.assist_metadata if isinstance(annotation.assist_metadata, dict) else {}
        raw = metadata.get("student_distribution") or metadata.get("phase_probabilities")
        if isinstance(raw, dict):
            raw_distributions.append(raw)
    classes = sorted({str(name) for dist in raw_distributions for name in dist})
    if not classes:
        return {
            "version": VERSION,
            "status": "insufficient_data",
            "message": "暂无小模型概率分布；运行人体姿态预标注并保存后才能分析。",
            "summary": {"analyzed": 0, "total_annotations": len(annotations)},
            "items": [],
        }

    prior_total = sum(labels.get(name, 0) + 1 for name in classes)
    prior = {name: (labels.get(name, 0) + 1) / prior_total for name in classes}
    prepared = []
    pairs = []
    for annotation in annotations:
        metadata = annotation.assist_metadata if isinstance(annotation.assist_metadata, dict) else {}
        student = _distribution(metadata.get("student_distribution") or metadata.get("phase_probabilities"), classes)
        teacher = _distribution(metadata.get("teacher_distribution"), classes)
        if student:
            prepared.append((annotation, student, teacher))
            if teacher:
                pairs.append((student, teacher))

    matrix = _learn_transition(pairs, classes)
    calibrated = len(pairs) >= max(10, len(classes) * 2)
    calibration_mae = None
    if pairs:
        errors = []
        for student, teacher in pairs:
            estimate = _project(student, matrix, prior, calibrated=True)
            errors.extend(abs(estimate[name] - teacher[name]) for name in classes)
        calibration_mae = sum(errors) / len(errors)

    previous_by_player: dict[int | None, tuple[int, dict[str, float]]] = {}
    items = []
    issue_counts = Counter()
    for annotation, student, teacher in prepared:
        estimate = teacher or _project(student, matrix, prior, calibrated)
        model_gap = _js_divergence(student, estimate)
        entropy = _entropy(student)
        label_conflict = 0.0
        if annotation.action_phase in estimate:
            label_conflict = 1.0 - estimate[annotation.action_phase]

        temporal_jump = 0.0
        previous = previous_by_player.get(annotation.selected_player_id)
        if previous and annotation.frame_index - previous[0] <= 2:
            temporal_jump = _js_divergence(previous[1], student)
        previous_by_player[annotation.selected_player_id] = (annotation.frame_index, student)

        frame = frames.get(annotation.frame_index)
        redundancy = 1.0 - max(0.0, min(1.0, float(frame.selection_score or 0.0))) if frame else 0.5
        quality_risk = min(1.0, 0.35 * label_conflict + 0.25 * model_gap + 0.25 * temporal_jump + 0.15 * redundancy)

        flags = []
        if label_conflict >= 0.65:
            flags.append("标签与预测分布冲突")
            issue_counts["label_conflict"] += 1
        if model_gap >= 0.25:
            flags.append("大小模型分歧高")
            issue_counts["model_gap"] += 1
        if temporal_jump >= 0.35:
            flags.append("相邻帧分布跳变")
            issue_counts["temporal_jump"] += 1
        if redundancy >= 0.85 and entropy <= 0.45:
            flags.append("疑似低信息重复样本")
            issue_counts["redundant"] += 1
        if entropy >= 0.80 and not flags:
            flags.append("高价值难样本（不等于错标）")
            issue_counts["hard_sample"] += 1

        items.append({
            "annotation_id": annotation.id,
            "frame_index": annotation.frame_index,
            "selected_player_id": annotation.selected_player_id,
            "student_distribution": {key: round(value, 4) for key, value in student.items()},
            "estimated_teacher_distribution": {key: round(value, 4) for key, value in estimate.items()},
            "teacher_source": "observed" if teacher else ("calibrated_surrogate" if calibrated else "uncalibrated_surrogate"),
            "entropy": round(entropy, 4),
            "model_gap": round(model_gap, 4),
            "label_conflict": round(label_conflict, 4),
            "temporal_jump": round(temporal_jump, 4),
            "redundancy": round(redundancy, 4),
            "quality_risk": round(quality_risk, 4),
            "flags": flags,
        })

    risky = sum(item["quality_risk"] >= 0.55 for item in items)
    return {
        "version": VERSION,
        "status": "calibrated" if calibrated else "uncalibrated",
        "message": (
            "已用真实教师分布校准小模型到大模型的映射。"
            if calibrated else
            "当前为未校准代理分布，不代表大模型真实输出；至少需要 10 条且每类约 2 条配对教师分布进行校准。"
        ),
        "classes": classes,
        "calibration": {
            "paired_samples": len(pairs),
            "minimum_recommended": max(10, len(classes) * 2),
            "mean_absolute_error": round(calibration_mae, 4) if calibration_mae is not None else None,
        },
        "summary": {
            "total_annotations": len(annotations),
            "analyzed": len(items),
            "coverage": round(len(items) / max(1, len(annotations)), 4),
            "high_risk": risky,
            "high_risk_ratio": round(risky / max(1, len(items)), 4),
            "issue_counts": dict(issue_counts),
        },
        "items": sorted(items, key=lambda item: item["quality_risk"], reverse=True),
    }
