"""Validation helpers for continuous temporal annotations."""

from typing import Optional


def validate_segment_range(start_frame: int, end_frame: int, total_frames: int) -> None:
    if total_frames < 1:
        raise ValueError("任务没有可标注帧")
    if start_frame < 1 or end_frame < 1:
        raise ValueError("帧编号必须从 1 开始")
    if end_frame < start_frame:
        raise ValueError("结束帧不能早于开始帧")
    if end_frame > total_frames:
        raise ValueError(f"片段结束帧超出任务范围（最大 {total_frames}）")


def ranges_overlap(
    start_frame: int,
    end_frame: int,
    other_start: int,
    other_end: int,
) -> bool:
    return start_frame <= other_end and other_start <= end_frame


def validate_segment_taxonomy(
    action_type: str,
    action_phase: Optional[str],
    taxonomy: dict,
) -> None:
    actions = {item["value"] for item in taxonomy.get("actions", [])}
    phases = {item["value"] for item in taxonomy.get("phases", [])}
    if action_type not in actions:
        raise ValueError(f"动作类型不在当前规范中: {action_type}")
    if action_phase is not None and action_phase not in phases:
        raise ValueError(f"动作阶段不在当前规范中: {action_phase}")
