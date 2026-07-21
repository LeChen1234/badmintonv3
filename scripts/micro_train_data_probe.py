"""Fast, dependency-light data utility probe for exported pose annotations.

Example:
  python scripts/micro_train_data_probe.py \
    --baseline old.json --curated new.json --test expert_holdout.json

The expert test set is never used for fitting or normalization. The probe is a
multinomial linear classifier over body-normalized pose coordinates and
visibility masks. Its purpose is A/B evaluation of data, not SOTA modeling.
"""

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np


KEYPOINTS = [
    "head_top", "head_center", "chin", "neck", "chest_center", "spine_mid", "pelvis_center",
    "left_shoulder", "left_elbow", "left_wrist", "left_palm", "right_shoulder", "right_elbow",
    "right_wrist", "right_palm", "left_hip", "left_knee", "left_ankle", "left_toe",
    "right_hip", "right_knee", "right_ankle", "right_toe", "racket_grip", "racket_head",
]


def load_records(paths: Sequence[Path]) -> List[dict]:
    records: List[dict] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("annotations", payload) if isinstance(payload, dict) else payload
        if not isinstance(values, list):
            raise ValueError(f"Unsupported export format: {path}")
        records.extend(item for item in values if isinstance(item, dict))
    return records


def export_dataset_id(paths: Sequence[Path]) -> str | None:
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    manifest = payload.get("release_manifest")
    return str(manifest.get("dataset_id")) if isinstance(manifest, dict) and manifest.get("dataset_id") else None


def pose_feature(record: dict) -> np.ndarray | None:
    raw = record.get("keypoints")
    if not isinstance(raw, list):
        return None
    points = {item.get("name"): item for item in raw if isinstance(item, dict) and item.get("name")}
    visible_xy = []
    for name in KEYPOINTS[:-2]:
        item = points.get(name, {})
        if int(item.get("visibility", 0) or 0) > 0:
            visible_xy.append((float(item.get("x", 0)), float(item.get("y", 0))))
    if len(visible_xy) < 8:
        return None
    center = np.mean(np.asarray(visible_xy, dtype=np.float64), axis=0)
    scale = float(np.sqrt(np.mean(np.sum((np.asarray(visible_xy) - center) ** 2, axis=1))))
    if scale <= 1e-6:
        return None
    coordinates, mask = [], []
    for name in KEYPOINTS:
        item = points.get(name, {})
        visible = int(item.get("visibility", 0) or 0) > 0
        if visible:
            coordinates.extend([
                (float(item.get("x", 0)) - center[0]) / scale,
                (float(item.get("y", 0)) - center[1]) / scale,
            ])
        else:
            coordinates.extend([0.0, 0.0])
        mask.append(1.0 if visible else 0.0)
    return np.asarray(coordinates + mask, dtype=np.float64)


def matrix(records: Sequence[dict], label_key: str) -> Tuple[np.ndarray, List[str], Dict[str, int]]:
    features, labels, groups = [], [], {}
    for record in records:
        feature = pose_feature(record)
        label = str(record.get(label_key, "")).strip()
        if feature is None or not label:
            continue
        features.append(feature)
        labels.append(label)
        group = record_group(record)
        groups[group] = groups.get(group, 0) + 1
    if not features:
        return np.empty((0, len(KEYPOINTS) * 3)), [], groups
    return np.vstack(features), labels, groups


def record_group(record: dict) -> str:
    """Return a stable leakage-control group, preferring match identity."""
    research_group = record.get("research_group")
    if isinstance(research_group, dict) and research_group.get("value"):
        return f"research:{research_group['value']}"
    return str(
        record.get("subject_code")
        or record.get("match_uuid")
        or record.get("task_batch_uuid")
        or (f"legacy-batch:{record['task_batch_id']}" if record.get("task_batch_id") is not None else "unknown")
    )


def usable_records(records: Sequence[dict], label_key: str) -> List[dict]:
    return [r for r in records if str(r.get(label_key, "")).strip() and pose_feature(r) is not None]


def equalize_training_sets(
    baseline: Sequence[dict], curated: Sequence[dict], label_key: str, seed: int = 20260721
) -> Tuple[List[dict], List[dict], Dict[str, int]]:
    """Stratify both arms to exactly the same per-class training budget."""
    rng = np.random.default_rng(seed)
    by_arm = []
    for records in (baseline, curated):
        grouped: Dict[str, List[dict]] = {}
        for record in usable_records(records, label_key):
            grouped.setdefault(str(record[label_key]).strip(), []).append(record)
        by_arm.append(grouped)
    shared = sorted(set(by_arm[0]) & set(by_arm[1]))
    budget = {label: min(len(by_arm[0][label]), len(by_arm[1][label])) for label in shared}
    budget = {label: count for label, count in budget.items() if count > 0}
    if len(budget) < 2:
        raise ValueError("Equal-budget A/B requires at least two shared classes")
    outputs = []
    for grouped in by_arm:
        selected = []
        for label, count in budget.items():
            indices = rng.choice(len(grouped[label]), size=count, replace=False)
            selected.extend(grouped[label][int(i)] for i in indices)
        outputs.append(selected)
    return outputs[0], outputs[1], budget


def assert_group_isolation(train_records: Sequence[dict], test_records: Sequence[dict], arm: str) -> None:
    train_groups = {record_group(r) for r in train_records}
    test_groups = {record_group(r) for r in test_records}
    overlap = sorted((train_groups & test_groups) - {"unknown"})
    if overlap:
        preview = ", ".join(overlap[:5])
        raise ValueError(f"{arm} train/test group leakage detected: {preview}")


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def fit_probe(x: np.ndarray, y: np.ndarray, classes: int, seed: int, epochs: int = 300):
    rng = np.random.default_rng(seed)
    mean, std = x.mean(axis=0), x.std(axis=0)
    std[std < 1e-6] = 1.0
    z = (x - mean) / std
    weights = rng.normal(0, 0.01, size=(z.shape[1], classes))
    bias = np.zeros(classes)
    counts = np.bincount(y, minlength=classes).astype(float)
    class_weights = len(y) / (classes * np.maximum(counts, 1.0))
    lr, l2 = 0.08, 1e-3
    for epoch in range(epochs):
        probability = softmax(z @ weights + bias)
        target = np.eye(classes)[y]
        error = (probability - target) * class_weights[y, None] / len(y)
        weights -= lr * (z.T @ error + l2 * weights)
        bias -= lr * error.sum(axis=0)
        lr *= 0.995
    return weights, bias, mean, std


def metrics(probability: np.ndarray, truth: np.ndarray) -> Dict[str, float]:
    prediction = probability.argmax(axis=1)
    classes = probability.shape[1]
    recalls, f1s = [], []
    for label in range(classes):
        tp = int(np.sum((prediction == label) & (truth == label)))
        fp = int(np.sum((prediction == label) & (truth != label)))
        fn = int(np.sum((prediction != label) & (truth == label)))
        if tp + fn:
            recalls.append(tp / (tp + fn))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    nll = -float(np.mean(np.log(np.maximum(probability[np.arange(len(truth)), truth], 1e-12))))
    confidence = probability.max(axis=1)
    correct = (prediction == truth).astype(float)
    ece = 0.0
    for low in np.linspace(0, 0.9, 10):
        selected = (confidence >= low) & (confidence < low + 0.1)
        if selected.any():
            ece += float(selected.mean()) * abs(float(correct[selected].mean()) - float(confidence[selected].mean()))
    return {
        "accuracy": float(correct.mean()),
        "balanced_accuracy": float(np.mean(recalls)) if recalls else 0.0,
        "macro_f1": float(np.mean(f1s)),
        "nll": nll,
        "ece": ece,
    }


def evaluate(train_records, test_records, label_key: str, repeats: int) -> Dict:
    x_train, train_labels, train_groups = matrix(train_records, label_key)
    x_test, test_labels, test_groups = matrix(test_records, label_key)
    labels = sorted(set(train_labels) | set(test_labels))
    if len(labels) < 2 or len(x_train) < 10 or len(x_test) < 5:
        raise ValueError(
            f"Need >=2 classes, >=10 usable train poses and >=5 test poses; "
            f"got classes={len(labels)}, train={len(x_train)}, test={len(x_test)}"
        )
    index = {label: i for i, label in enumerate(labels)}
    y_train = np.asarray([index[label] for label in train_labels])
    y_test = np.asarray([index[label] for label in test_labels])
    runs, probabilities = [], []
    for seed in range(repeats):
        weights, bias, mean, std = fit_probe(x_train, y_train, len(labels), seed)
        probability = softmax(((x_test - mean) / std) @ weights + bias)
        probabilities.append(probability)
        runs.append(metrics(probability, y_test))
    summary = {
        key: {"mean": float(np.mean([run[key] for run in runs])), "std": float(np.std([run[key] for run in runs]))}
        for key in runs[0]
    }
    return {
        "usable_train": len(x_train), "usable_test": len(x_test), "classes": labels,
        "train_groups": train_groups, "test_groups": test_groups, "metrics": summary,
        "_average_probability": np.mean(probabilities, axis=0), "_truth": y_test,
    }


def paired_bootstrap(
    baseline_probability: np.ndarray,
    curated_probability: np.ndarray,
    truth: np.ndarray,
    iterations: int = 2000,
    seed: int = 20260721,
) -> Dict[str, dict]:
    """Paired resampling keeps the same holdout items in both experimental arms."""
    if baseline_probability.shape != curated_probability.shape or len(truth) != len(baseline_probability):
        raise ValueError("Paired bootstrap requires aligned predictions on the same holdout")
    rng = np.random.default_rng(seed)
    deltas = {"macro_f1": [], "balanced_accuracy": [], "accuracy": []}
    for _ in range(iterations):
        indices = rng.integers(0, len(truth), size=len(truth))
        baseline_metrics = metrics(baseline_probability[indices], truth[indices])
        curated_metrics = metrics(curated_probability[indices], truth[indices])
        for name in deltas:
            deltas[name].append(curated_metrics[name] - baseline_metrics[name])
    result = {}
    for name, values in deltas.items():
        array = np.asarray(values)
        probability_positive = float(np.mean(array > 0))
        result[name] = {
            "mean_delta": float(np.mean(array)),
            "ci95": [float(np.percentile(array, 2.5)), float(np.percentile(array, 97.5))],
            "probability_curated_better": probability_positive,
            "two_sided_p": float(min(1.0, 2 * min(np.mean(array <= 0), np.mean(array >= 0)))),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B micro-training probe for annotation data utility")
    parser.add_argument("--baseline", type=Path, nargs="+", required=True, help="Old-process training exports")
    parser.add_argument("--curated", type=Path, nargs="+", required=True, help="New-process training exports")
    parser.add_argument("--test", type=Path, nargs="+", required=True, help="Frozen expert holdout exports")
    parser.add_argument("--label", choices=["action_type", "action_phase", "quality_rating"], default="action_type")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--bootstrap", type=int, default=2000, help="Paired holdout bootstrap iterations")
    parser.add_argument("--unequal-budget", action="store_true", help="Disable default per-class equal-budget A/B")
    parser.add_argument("--allow-group-overlap", action="store_true", help="Unsafe diagnostic override for train/test leakage")
    parser.add_argument("--output", type=Path, default=Path("data/exports/micro_train_report.json"))
    args = parser.parse_args()

    test = load_records(args.test)
    baseline = load_records(args.baseline)
    curated = load_records(args.curated)
    budget = None
    if not args.unequal_budget:
        baseline, curated, budget = equalize_training_sets(baseline, curated, args.label)
    if not args.allow_group_overlap:
        assert_group_isolation(baseline, test, "baseline")
        assert_group_isolation(curated, test, "curated")
    baseline_result = evaluate(baseline, test, args.label, args.repeats)
    curated_result = evaluate(curated, test, args.label, args.repeats)
    statistical_comparison = paired_bootstrap(
        baseline_result.pop("_average_probability"), curated_result.pop("_average_probability"),
        baseline_result.pop("_truth"), iterations=args.bootstrap,
    )
    curated_result.pop("_truth")
    report = {
        "protocol": "frozen expert holdout; group-isolated; per-class equal-budget; body-normalized pose linear probe",
        "label": args.label,
        "repeats": args.repeats,
        "bootstrap_iterations": args.bootstrap,
        "equal_budget_per_class": budget,
        "baseline": baseline_result,
        "curated": curated_result,
        "statistical_comparison": statistical_comparison,
    }
    b, c = report["baseline"]["metrics"], report["curated"]["metrics"]
    report["delta_curated_minus_baseline"] = {
        key: c[key]["mean"] - b[key]["mean"] for key in b
    }
    duration_ms = sum(
        float(record.get("annotation_duration_ms", 0) or 0)
        for record in curated if isinstance(record.get("annotation_duration_ms"), (int, float))
    )
    report["research_import"] = {
        "dataset_id": export_dataset_id(args.curated),
        "model_version": "pose-linear-probe-v1",
        "annotation_count": curated_result["usable_train"],
        "annotation_hours": duration_ms / 3_600_000,
        "macro_f1_mean": c["macro_f1"]["mean"],
        "macro_f1_std": c["macro_f1"]["std"],
        "repeat_count": args.repeats,
        "balanced_accuracy_mean": c["balanced_accuracy"]["mean"],
        "nll_mean": c["nll"]["mean"],
        "ece_mean": c["ece"]["mean"],
        "component_gains": {},
        "statistical_comparison": statistical_comparison,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["delta_curated_minus_baseline"], ensure_ascii=False, indent=2))
    print(f"Full report: {args.output}")


if __name__ == "__main__":
    main()
