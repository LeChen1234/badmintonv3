from datetime import datetime
from typing import Optional

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


class TaskBatchOut(BaseModel):
    id: int
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
