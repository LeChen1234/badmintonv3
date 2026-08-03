"""Validation and reader-facing guidance for badminton capture protocols."""

from __future__ import annotations

from typing import Any, Mapping


CAPTURE_MODES = {"competition", "controlled_training"}
ANNOTATION_GOALS = {"action_sequence", "technique_quality"}
CAMERA_VIEWS = {
    "front",
    "rear",
    "left",
    "right",
    "front_left",
    "front_right",
    "rear_left",
    "rear_right",
    "other",
}
CAMERA_HEIGHTS = {"low", "eye_level", "high", "unknown"}
MARKER_PROTOCOLS = {"video_landmarks", "physical_markers"}
RECORDING_DESIGNS = {"natural_training", "prescribed_standard", "prescribed_variation", "mixed"}
FEED_METHODS = {"coach", "machine", "self", "rally", "unknown"}


def normalize_capture_metadata(
    value: Mapping[str, Any] | None,
    *,
    match_format: str | None = None,
) -> dict[str, Any]:
    """Return a bounded, stable metadata object.

    Old tasks did not store a protocol. They remain compatible and are treated as
    competition/action-sequence tasks until an operator explicitly updates them.
    """

    raw = dict(value or {})
    capture_mode = raw.get("capture_mode")
    if capture_mode not in CAPTURE_MODES:
        capture_mode = "competition" if match_format in {"singles", "doubles"} else "controlled_training"

    annotation_goal = raw.get("annotation_goal")
    if annotation_goal not in ANNOTATION_GOALS:
        annotation_goal = "action_sequence" if capture_mode == "competition" else "technique_quality"

    camera_view = raw.get("camera_view")
    if camera_view not in CAMERA_VIEWS:
        camera_view = None

    camera_height = raw.get("camera_height")
    if camera_height not in CAMERA_HEIGHTS:
        camera_height = "unknown"

    marker_protocol = raw.get("marker_protocol")
    if marker_protocol not in MARKER_PROTOCOLS:
        marker_protocol = "video_landmarks"

    recording_design = raw.get("recording_design")
    if recording_design not in RECORDING_DESIGNS:
        recording_design = None

    feed_method = raw.get("feed_method")
    if feed_method not in FEED_METHODS:
        feed_method = None

    try:
        recording_fps = float(raw.get("recording_fps")) if raw.get("recording_fps") not in (None, "") else None
    except (TypeError, ValueError):
        recording_fps = None
    if recording_fps is not None and not 1 <= recording_fps <= 1000:
        recording_fps = None

    def clean_text(key: str, max_length: int) -> str | None:
        text = str(raw.get(key) or "").strip()
        return text[:max_length] or None

    normalized = {
        "capture_mode": capture_mode,
        "annotation_goal": annotation_goal,
        "camera_view": camera_view,
        "camera_height": camera_height,
        "capture_session_id": clean_text("capture_session_id", 64),
        "target_action": clean_text("target_action", 128),
        "marker_protocol": marker_protocol,
        "recording_notes": clean_text("recording_notes", 512),
        "source_reference": clean_text("source_reference", 512),
        "source_platform": clean_text("source_platform", 64),
        "device_model": clean_text("device_model", 128),
        "recording_fps": recording_fps,
        "recording_design": recording_design,
        "feed_method": feed_method,
        "repetition_group_id": clean_text("repetition_group_id", 64),
        "bridge_view_id": clean_text("bridge_view_id", 64),
        "intended_variation": clean_text("intended_variation", 256),
    }
    if capture_mode == "competition":
        for key in (
            "device_model",
            "recording_fps",
            "recording_design",
            "feed_method",
            "repetition_group_id",
            "bridge_view_id",
            "intended_variation",
        ):
            normalized[key] = None
    else:
        normalized["source_reference"] = None
        normalized["source_platform"] = None
    return normalized


def validate_capture_protocol(
    *,
    capture_metadata: Mapping[str, Any] | None,
    match_format: str | None,
    match_name: str | None,
    match_date: Any,
    player_count: int,
) -> list[str]:
    protocol = normalize_capture_metadata(capture_metadata, match_format=match_format)
    errors: list[str] = []

    if not (match_name or "").strip():
        errors.append("请填写比赛或采集任务名称")
    if not match_date:
        errors.append("请选择比赛或拍摄日期")
    if not protocol["camera_view"]:
        errors.append("请选择拍摄视角")

    if protocol["capture_mode"] == "competition":
        if protocol["annotation_goal"] != "action_sequence":
            errors.append("比赛远景视频只能使用动作时序/战术标注轨")
        expected = 2 if match_format == "singles" else 4 if match_format == "doubles" else 0
        if not expected:
            errors.append("比赛视频请选择单打或双打")
        elif player_count != expected:
            label = "单打" if match_format == "singles" else "双打"
            errors.append(f"{label}比赛必须填写 {expected} 名运动员")
        if protocol["marker_protocol"] == "physical_markers":
            errors.append("反光/实体标记点方案仅适用于受控抵近训练采集")
        if not protocol["source_reference"]:
            errors.append("网络比赛视频必须填写来源链接或来源编号")
    else:
        if player_count < 1:
            errors.append("受控训练至少填写 1 名受试者")
        if player_count > 4:
            errors.append("单个受控训练任务最多填写 4 名受试者")
        if not protocol["recording_design"]:
            errors.append("手机训练视频必须选择自然训练或指定动作采集方式")
        if not protocol["recording_fps"]:
            errors.append("手机训练视频必须填写实际拍摄帧率")

    if protocol["annotation_goal"] == "technique_quality" and not protocol["target_action"]:
        errors.append("精细动作质量轨必须填写目标动作")
    if protocol["marker_protocol"] == "physical_markers":
        if protocol["capture_mode"] != "controlled_training":
            errors.append("实体标记点方案必须使用受控训练场景")
        if protocol["annotation_goal"] != "technique_quality":
            errors.append("实体标记点方案必须使用精细动作质量轨")

    return list(dict.fromkeys(errors))


def capture_protocol_advisory(capture_metadata: Mapping[str, Any] | None, *, match_format: str | None = None) -> dict[str, Any]:
    protocol = normalize_capture_metadata(capture_metadata, match_format=match_format)
    if protocol["annotation_goal"] == "technique_quality":
        return {
            "code": "technique_quality",
            "title": "抵近训练质量轨",
            "message": "用于动作阶段、技术质量和可见的球拍接触细节；必须保留完整动作序列，遮挡或模糊处不得猜测。",
            "fine_quality_enabled": True,
        }
    return {
        "code": "action_sequence",
        "title": "比赛/动作时序轨",
        "message": "用于动作类别、时序、受迫性、移动与战术；不把远景画面用于精细生物力学质量结论。",
        "fine_quality_enabled": False,
    }
