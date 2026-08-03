from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.annotation import AnnotationStatus


class StrokeContext(BaseModel):
    incoming_height: Optional[Literal["low", "mid", "high", "unknown"]] = None
    incoming_depth: Optional[Literal["front", "mid", "rear", "unknown"]] = None
    incoming_direction: Optional[Literal["forehand", "body", "backhand", "unknown"]] = None
    pressure_state: Optional[Literal["attacking", "neutral", "forced", "unknown"]] = None
    preparation_time: Optional[Literal["sufficient", "limited", "very_late", "unknown"]] = None
    balance_before: Optional[Literal["stable", "moving", "off_balance", "unknown"]] = None


class StrokeExecution(BaseModel):
    arrival_state: Optional[Literal["early", "on_time", "late", "unknown"]] = None
    movement_pattern: Optional[str] = Field(default=None, max_length=64)
    contact_relative_position: Optional[Literal["front", "side", "behind", "unknown"]] = None
    landing_stability: Optional[Literal["stable", "recoverable", "unstable", "unknown"]] = None
    recovery_quality: Optional[Literal["good", "partial", "poor", "unknown"]] = None
    error_mechanisms: list[
        Literal[
            "late_start", "poor_arrival", "contact_behind", "off_balance",
            "limited_trunk_rotation", "arm_coordination", "unstable_landing", "slow_recovery",
        ]
    ] = Field(default_factory=list, max_length=12)


class StrokeOutcome(BaseModel):
    outgoing_height: Optional[Literal["low", "mid", "high", "unknown"]] = None
    landing_depth: Optional[Literal["front", "mid", "rear", "out", "net", "unknown"]] = None
    opponent_response: Optional[Literal["attacking", "neutral", "forced", "no_return", "unknown"]] = None
    rally_effect: Optional[Literal["advantage", "neutral", "disadvantage", "winner", "error", "unknown"]] = None


class StrokeEvidence(BaseModel):
    context_visibility: Literal["clear", "partial", "unknown"] = "unknown"
    contact_visibility: Literal["clear", "inferred", "not_visible"] = "not_visible"
    outcome_visibility: Literal["clear", "partial", "unknown"] = "unknown"
    confidence: int = Field(default=3, ge=1, le=5)
    basis: Literal["direct_video", "adjacent_frames", "controlled_instruction", "expert_inference"] = "direct_video"


class TemporalSegmentCreate(BaseModel):
    task_batch_id: int
    selected_player_id: int
    start_frame: int = Field(ge=1)
    end_frame: int = Field(ge=1)
    action_type: str = Field(min_length=1, max_length=64)
    action_phase: Optional[str] = Field(default=None, max_length=64)
    context: Optional[StrokeContext] = None
    execution: Optional[StrokeExecution] = None
    outcome: Optional[StrokeOutcome] = None
    evidence: Optional[StrokeEvidence] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_frame < self.start_frame:
            raise ValueError("结束帧不能早于开始帧")
        return self


class TemporalSegmentUpdate(BaseModel):
    selected_player_id: Optional[int] = None
    start_frame: Optional[int] = Field(default=None, ge=1)
    end_frame: Optional[int] = Field(default=None, ge=1)
    action_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    action_phase: Optional[str] = Field(default=None, max_length=64)
    context: Optional[StrokeContext] = None
    execution: Optional[StrokeExecution] = None
    outcome: Optional[StrokeOutcome] = None
    evidence: Optional[StrokeEvidence] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class TemporalSegmentOut(BaseModel):
    id: int
    uuid: str
    task_batch_id: int
    selected_player_id: int
    annotator_id: int
    annotator_name: str
    start_frame: int
    end_frame: int
    start_timestamp_ms: int
    end_timestamp_ms: int
    action_type: str
    action_phase: Optional[str] = None
    context: Optional[dict] = None
    execution: Optional[dict] = None
    outcome: Optional[dict] = None
    evidence: Optional[dict] = None
    notes: Optional[str] = None
    status: AnnotationStatus
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TemporalSegmentConfirmRequest(BaseModel):
    segment_ids: list[int] = Field(min_length=1, max_length=1000)
