from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.task_batch import MediaProcessStatus, TaskStatus


class TaskBatchCreate(BaseModel):
    project_id: int
    name: str = Field(..., min_length=1, max_length=256)
    action_category: Optional[str] = None
    assigned_to: Optional[int] = None
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    total_frames: int = 0
    deadline: Optional[datetime] = None


class TaskBatchUpdate(BaseModel):
    name: Optional[str] = None
    action_category: Optional[str] = None
    assigned_to: Optional[int] = None
    deadline: Optional[datetime] = None


class TaskPlayerInfo(BaseModel):
    id: Optional[int] = None
    uuid: Optional[str] = Field(default=None, max_length=36)
    name: Optional[str] = Field(default=None, max_length=128)
    gender: Optional[str] = Field(default=None, max_length=16)
    age: Optional[int] = Field(default=None, ge=1, le=99)
    height_cm: Optional[int] = Field(default=None, ge=80, le=260)


class TaskBatchMetadataUpdate(BaseModel):
    match_date: Optional[date] = Field(default=None)
    match_name: Optional[str] = Field(default=None, max_length=256)
    players: Optional[List[TaskPlayerInfo]] = None


class TaskBatchOut(BaseModel):
    id: int
    uuid: str
    project_id: int
    name: str
    action_category: Optional[str] = None
    assigned_to: Optional[int] = None
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
    players: List[TaskPlayerInfo] = Field(default_factory=list)
    metadata_confirmed: bool = False
    metadata_confirmed_at: Optional[datetime] = None
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

    model_config = {"from_attributes": True}
