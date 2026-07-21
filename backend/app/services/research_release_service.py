"""Deterministic, leakage-aware metadata for reproducible dataset releases."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from app.config import settings


def load_research_protocol() -> Dict[str, Any]:
    path = Path(settings.RESEARCH_PROTOCOL_PATH).resolve()
    if not path.is_file():
        raise RuntimeError(f"Research protocol not found: {path}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    splits = protocol.get("splits", {})
    if not splits or any(float(value) <= 0 for value in splits.values()):
        raise RuntimeError("Research splits must all be positive")
    if abs(sum(float(value) for value in splits.values()) - 1.0) > 1e-8:
        raise RuntimeError("Research split ratios must sum to 1")
    if not protocol.get("group_key_priority"):
        raise RuntimeError("Research protocol requires group_key_priority")
    return protocol


def canonical_fingerprint(records: Sequence[dict]) -> str:
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _group(record: dict, priorities: Sequence[str]) -> Tuple[str, str]:
    for key in priorities:
        value = record.get(key)
        if value:
            return key, str(value)
    return "missing", f"annotation:{record.get('annotation_id', 'unknown')}"


def _connected_groups(records: Sequence[dict], priorities: Sequence[str]) -> list:
    """Join records sharing any subject or match identity into one split component."""
    parent = {}

    def find(value):
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left, right):
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    identifiers_per_record = []
    for record in records:
        identifiers = [f"{key}:{record[key]}" for key in priorities if record.get(key)]
        identifiers_per_record.append(identifiers)
        if identifiers:
            find(identifiers[0])
        for identifier in identifiers[1:]:
            union(identifiers[0], identifier)
    components = {}
    for identifier in list(parent):
        components.setdefault(find(identifier), []).append(identifier)
    component_ids = {
        root: hashlib.sha256("|".join(sorted(values)).encode("utf-8")).hexdigest()[:16]
        for root, values in components.items()
    }
    result = []
    for index, identifiers in enumerate(identifiers_per_record):
        if not identifiers:
            result.append(("missing", f"annotation:{records[index].get('annotation_id', 'unknown')}"))
        else:
            result.append(("connected_identity", component_ids[find(identifiers[0])]))
    return result


def _split_for_group(group: str, seed: str, splits: Dict[str, float]) -> str:
    digest = hashlib.sha256(f"{seed}:{group}".encode("utf-8")).digest()
    position = int.from_bytes(digest[:8], "big") / float(2**64)
    cumulative = 0.0
    for name, ratio in splits.items():
        cumulative += float(ratio)
        if position < cumulative:
            return name
    return next(reversed(splits))


def build_release(
    records: Sequence[dict], project_uuid: str, protocol: Optional[dict] = None, *, only_locked_batches: bool = True
) -> Tuple[list, dict]:
    protocol = protocol or load_research_protocol()
    priorities = list(protocol["group_key_priority"])
    splits = {name: float(value) for name, value in protocol["splits"].items()}
    seed = str(protocol["split_seed"])
    source_records = deepcopy(list(records))
    fingerprint = canonical_fingerprint(source_records)
    released, group_splits, missing = [], {}, 0
    connected_groups = _connected_groups(source_records, priorities)
    for source, (group_key, group) in zip(source_records, connected_groups):
        record = deepcopy(source)
        missing += int(group_key == "missing")
        split = _split_for_group(group, f"{seed}:{project_uuid}", splits)
        previous = group_splits.setdefault(group, split)
        if previous != split:
            raise RuntimeError(f"Group assigned to multiple splits: {group}")
        record["research_split"] = split
        record["research_group"] = {"key": group_key, "value": group}
        released.append(record)
    counts = {name: sum(r["research_split"] == name for r in released) for name in splits}
    requirements = protocol.get("release_requirements", {})
    action_classes = len({r.get("action_type") for r in released if r.get("action_type")})
    usable_poses = 0
    for record in released:
        points = record.get("keypoints")
        if isinstance(points, list) and sum(
            int(point.get("visibility", 0) or 0) > 0 for point in points if isinstance(point, dict)
        ) >= 8:
            usable_poses += 1
    pose_coverage = usable_poses / len(released) if released else 0.0
    gates = {
        "only_locked_batches": only_locked_batches,
        "stable_group_identity": missing == 0,
        "minimum_matches": len(group_splits) >= int(requirements.get("minimum_matches", 1)),
        "minimum_action_classes": action_classes >= int(requirements.get("minimum_action_classes", 2)),
        "minimum_pose_coverage": pose_coverage >= float(requirements.get("minimum_pose_coverage", 0.8)),
        "all_splits_non_empty": bool(released) and all(count > 0 for count in counts.values()),
    }
    warnings = []
    if missing:
        warnings.append("Some records lack a stable group identity")
    if released and any(count == 0 for count in counts.values()):
        warnings.append("At least one configured split is empty")
    if not all(gates.values()):
        warnings.append("Release quality gates failed; do not use as a paper benchmark")
    manifest = {
        "dataset_id": f"badminton-{fingerprint[:12]}", "sha256": fingerprint,
        "protocol_version": protocol.get("version"), "split_seed": seed,
        "split_ratios": splits, "group_key_priority": priorities,
        "record_count": len(released), "group_count": len(group_splits),
        "split_record_counts": counts, "missing_group_identity": missing,
        "action_class_count": action_classes, "pose_coverage": pose_coverage,
        "quality_gates": gates, "release_ready": all(gates.values()),
        "warnings": warnings,
    }
    return released, manifest
