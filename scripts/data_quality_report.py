"""Audit exported annotations before training or publication.

The report is deterministic and dependency-light. It checks schema/provenance,
pose completeness, label validity, class balance, group identity, and adjacent
frame redundancy. A failing gate means the export should not be used as a
paper result until the stated issue is resolved.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Sequence


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
        records.extend(value for value in values if isinstance(value, dict))
    return records


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] * (high - position) + ordered[high] * (position - low))


def normalized_entropy(counts: Counter) -> float:
    total, classes = sum(counts.values()), len(counts)
    if total == 0 or classes < 2:
        return 0.0
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    return entropy / math.log(classes)


def pose_signature(record: dict) -> tuple | None:
    raw = record.get("keypoints")
    if not isinstance(raw, list):
        return None
    points = {p.get("name"): p for p in raw if isinstance(p, dict) and p.get("name")}
    visible = []
    for name in KEYPOINTS:
        p = points.get(name, {})
        if int(p.get("visibility", 0) or 0) > 0:
            try:
                visible.append((float(p["x"]), float(p["y"])))
            except (KeyError, TypeError, ValueError):
                return None
    if len(visible) < 8:
        return None
    cx = sum(x for x, _ in visible) / len(visible)
    cy = sum(y for _, y in visible) / len(visible)
    scale = math.sqrt(sum((x - cx) ** 2 + (y - cy) ** 2 for x, y in visible) / len(visible))
    if scale <= 1e-6:
        return None
    signature = []
    for name in KEYPOINTS:
        p = points.get(name, {})
        if int(p.get("visibility", 0) or 0) > 0:
            signature.extend((round((float(p["x"]) - cx) / scale, 3), round((float(p["y"]) - cy) / scale, 3), 1))
        else:
            signature.extend((0, 0, 0))
    return tuple(signature)


def build_report(records: Sequence[dict], taxonomy: dict) -> dict:
    total = len(records)
    action_counts = Counter(str(r.get("action_type", "")).strip() for r in records if r.get("action_type"))
    allowed = {
        "action_type": {item["value"] for item in taxonomy.get("actions", [])},
        "action_phase": {item["value"] for item in taxonomy.get("phases", [])},
        "quality_rating": {item["value"] for item in taxonomy.get("qualities", [])},
    }
    invalid_labels = {
        field: sorted({str(r.get(field)) for r in records if r.get(field) and r.get(field) not in values})
        for field, values in allowed.items()
    }
    visible_counts = Counter()
    invalid_coordinates = 0
    usable_poses = 0
    signatures = Counter()
    for record in records:
        raw = record.get("keypoints")
        if isinstance(raw, list):
            for point in raw:
                if not isinstance(point, dict) or point.get("name") not in KEYPOINTS:
                    continue
                if int(point.get("visibility", 0) or 0) > 0:
                    visible_counts[point["name"]] += 1
                    try:
                        x, y = float(point["x"]), float(point["y"])
                        if not (math.isfinite(x) and math.isfinite(y) and 0 <= x <= 100 and 0 <= y <= 100):
                            invalid_coordinates += 1
                    except (KeyError, TypeError, ValueError):
                        invalid_coordinates += 1
        signature = pose_signature(record)
        if signature is not None:
            usable_poses += 1
            signatures[signature] += 1

    redundant_adjacent = 0
    comparable_adjacent = 0
    sequences: Dict[str, List[dict]] = defaultdict(list)
    group_splits: Dict[str, set] = defaultdict(set)
    identity_splits: Dict[str, set] = defaultdict(set)
    for record in records:
        group = str(record.get("match_uuid") or record.get("task_batch_uuid") or record.get("task_batch_id") or "unknown")
        sequences[group].append(record)
        if record.get("research_split"):
            group_splits[group].add(str(record["research_split"]))
            for identity_key in ("subject_code", "match_uuid"):
                if record.get(identity_key):
                    identity_splits[f"{identity_key}:{record[identity_key]}"].add(str(record["research_split"]))
    for sequence in sequences.values():
        sequence.sort(key=lambda r: int(r.get("frame_index", 0) or 0))
        for previous, current in zip(sequence, sequence[1:]):
            if int(current.get("frame_index", 0) or 0) - int(previous.get("frame_index", 0) or 0) != 1:
                continue
            a, b = pose_signature(previous), pose_signature(current)
            if a is not None and b is not None:
                comparable_adjacent += 1
                redundant_adjacent += int(a == b and previous.get("action_type") == current.get("action_type"))

    durations = [float(r["annotation_duration_ms"]) for r in records if isinstance(r.get("annotation_duration_ms"), (int, float)) and r["annotation_duration_ms"] >= 0]
    assist_known = [r for r in records if r.get("assist_accepted") is not None]
    provenance_fields = ("taxonomy_version", "annotation_duration_ms", "task_batch_uuid", "match_uuid", "selected_player_uuid")
    provenance = {field: sum(r.get(field) is not None for r in records) / total if total else 0.0 for field in provenance_fields}
    revised = [r for r in records if int(r.get("revision_count", 0) or 0) > 0]
    cross_split_groups = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    cross_split_identities = sorted(identity for identity, splits in identity_splits.items() if len(splits) > 1)
    duplicate_excess = sum(count - 1 for count in signatures.values() if count > 1)
    pose_coverage = usable_poses / total if total else 0.0
    gates = {
        "non_empty": total > 0,
        "pose_coverage_at_least_80pct": pose_coverage >= 0.8,
        "no_invalid_coordinates": invalid_coordinates == 0,
        "no_out_of_taxonomy_labels": not any(invalid_labels.values()),
        "at_least_two_action_classes": len(action_counts) >= 2,
        "stable_group_identity_at_least_95pct": provenance["match_uuid"] >= 0.95,
        "taxonomy_provenance_at_least_95pct": provenance["taxonomy_version"] >= 0.95,
        "no_group_crosses_research_splits": not cross_split_groups and not cross_split_identities,
    }
    return {
        "status": "pass" if all(gates.values()) else "fail",
        "quality_gates": gates,
        "records": {"total": total, "usable_pose": usable_poses, "pose_coverage": pose_coverage},
        "labels": {"action_distribution": dict(action_counts), "action_normalized_entropy": normalized_entropy(action_counts), "invalid": invalid_labels},
        "keypoints": {"visibility_rate": {name: visible_counts[name] / total if total else 0.0 for name in KEYPOINTS}, "invalid_coordinates": invalid_coordinates},
        "redundancy": {"exact_pose_duplicate_rate": duplicate_excess / usable_poses if usable_poses else 0.0, "adjacent_exact_rate": redundant_adjacent / comparable_adjacent if comparable_adjacent else 0.0, "comparable_adjacent_pairs": comparable_adjacent},
        "provenance_completeness": provenance,
        "annotation_process": {
            "duration_ms_median": median(durations) if durations else None,
            "duration_ms_p90": percentile(durations, 0.9),
            "assist_decision_coverage": len(assist_known) / total if total else 0.0,
            "assist_acceptance_rate": sum(bool(r.get("assist_accepted")) for r in assist_known) / len(assist_known) if assist_known else None,
            "human_correction_rate": len(revised) / total if total else 0.0,
            "mean_revisions_per_record": sum(int(r.get("revision_count", 0) or 0) for r in records) / total if total else 0.0,
        },
        "groups": {"count": len(sequences), "sizes": {key: len(value) for key, value in sequences.items()}, "cross_split_groups": cross_split_groups, "cross_split_identities": cross_split_identities},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Quality gate for annotation-system JSON exports")
    parser.add_argument("exports", nargs="+", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=Path("config/annotation_taxonomy.json"))
    parser.add_argument("--output", type=Path, default=Path("data/exports/data_quality_report.json"))
    args = parser.parse_args()
    taxonomy = json.loads(args.taxonomy.read_text(encoding="utf-8"))
    report = build_report(load_records(args.exports), taxonomy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "quality_gates": report["quality_gates"]}, ensure_ascii=False, indent=2))
    print(f"Full report: {args.output}")


if __name__ == "__main__":
    main()
