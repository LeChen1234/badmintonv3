from datetime import datetime, date
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.models.task_batch import MediaProcessStatus, TaskStatus


class TaskBatchCreate(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=256)
    action_category: Optional[str] = None
    assigned_to: Optional[int] = None
    secondary_assigned_to: Optional[int] = None
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    total_frames: int = 0
    deadline: Optional[datetime] = None


class TaskBatchUpdate(BaseModel):
    name: Optional[str] = None
    action_category: Optional[str] = None
    assigned_to: Optional[int] = None
    secondary_assigned_to: Optional[int] = None
    deadline: Optional[datetime] = None


class TaskPlayerInfo(BaseModel):
    id: Optional[int] = None
    uuid: Optional[str] = Field(default=None, max_length=36)
    name: Optional[str] = Field(default=None, max_length=128)
    subject_code: Optional[str] = Field(default=None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    gender: Optional[str] = Field(default=None, max_length=16)
    age: Optional[int] = Field(default=None, ge=1, le=99)
    height_cm: Optional[int] = Field(default=None, ge=80, le=260)
    racket_hand: Optional[str] = Field(default=None, pattern="^(left|right)$")


class CaptureMetadata(BaseModel):
    capture_mode: str = Field(default="competition", pattern="^(competition|controlled_training)$")
    annotation_goal: str = Field(default="action_sequence", pattern="^(action_sequence|technique_quality)$")
    camera_view: Optional[str] = Field(
        default=None,
        pattern="^(front|rear|left|right|front_left|front_right|rear_left|rear_right|other)$",
    )
    camera_height: str = Field(default="unknown", pattern="^(low|eye_level|high|unknown)$")
    capture_session_id: Optional[str] = Field(default=None, max_length=64)
    target_action: Optional[str] = Field(default=None, max_length=128)
    marker_protocol: str = Field(default="video_landmarks", pattern="^(video_landmarks|physical_markers)$")
    recording_notes: Optional[str] = Field(default=None, max_length=512)
    source_reference: Optional[str] = Field(default=None, max_length=512)
    source_platform: Optional[str] = Field(default=None, max_length=64)
    device_model: Optional[str] = Field(default=None, max_length=128)
    recording_fps: Optional[float] = Field(default=None, ge=1, le=1000)
    recording_design: Optional[str] = Field(
        default=None,
        pattern="^(natural_training|prescribed_standard|prescribed_variation|mixed)$",
    )
    feed_method: Optional[str] = Field(default=None, pattern="^(coach|machine|self|rally|unknown)$")
    repetition_group_id: Optional[str] = Field(default=None, max_length=64)
    bridge_view_id: Optional[str] = Field(default=None, max_length=64)
    intended_variation: Optional[str] = Field(default=None, max_length=256)


class TaskBatchMetadataUpdate(BaseModel):
    match_date: Optional[date] = Field(default=None)
    match_name: Optional[str] = Field(default=None, max_length=256)
    match_format: Optional[str] = Field(default=None, pattern="^(singles|doubles)$")
    capture_metadata: Optional[CaptureMetadata] = None
    players: Optional[List[TaskPlayerInfo]] = None


class TaskBatchOut(BaseModel):
    id: int
    uuid: str
    project_id: int
    name: str
    action_category: Optional[str] = None
    assigned_to: Optional[int] = None
    secondary_assigned_to: Optional[int] = None
    secondary_assignee_name: Optional[str] = None
    assignee_name: Optional[str] = None
    status: TaskStatus
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    total_frames: int
    completed_frames: int
    media_process_status: MediaProcessStatus
    media_process_message: Optional[str] = None
    media_process_started_at: Optional[datetime] = None
    media_process_finished_at: Optional[datetime] = None
    match_uuid: Optional[str] = None
    match_date: Optional[date] = None
    match_name: Optional[str] = None
    match_format: Optional[str] = None
    capture_metadata: Optional[Any] = None
    capture_protocol_advisory: Optional[Any] = None
    players: List[TaskPlayerInfo] = Field(default_factory=list)
    metadata_confirmed: bool = False
    metadata_confirmed_at: Optional[datetime] = None
    selection_metadata: Optional[Any] = None
    video_id: Optional[str] = None
    video_sha256: Optional[str] = None
    video_filename: Optional[str] = None
    deadline: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskBatchMediaProcessOut(BaseModel):
    task_batch_id: int
    media_process_status: MediaProcessStatus
    media_process_message: Optional[str] = None
    media_process_started_at: Optional[datetime] = None
    media_process_finished_at: Optional[datetime] = None
    total_frames: int
    video_id: Optional[str] = None

    model_config = {"from_attributes": True}
