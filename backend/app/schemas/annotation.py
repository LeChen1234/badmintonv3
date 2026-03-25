from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from app.models.annotation import AnnotationStatus


class KeypointData(BaseModel):
    name: str
    x: float
    y: float
    visibility: int = 2


class FrameAnnotationCreate(BaseModel):
    task_batch_id: int
    frame_index: int
    keypoints: Optional[List[KeypointData]] = None
    box_x: Optional[float] = None
    box_y: Optional[float] = None
    box_w: Optional[float] = None
    box_h: Optional[float] = None
    selected_player_id: Optional[int] = Field(default=None)
    action_type: Optional[str] = None
    action_phase: Optional[str] = None
    quality_rating: Optional[str] = None
    is_forced_action: bool = False
    notes: Optional[str] = None
    is_ml_generated: bool = False


class FrameAnnotationUpdate(BaseModel):
    keypoints: Optional[List[KeypointData]] = None
    box_x: Optional[float] = None
    box_y: Optional[float] = None
    box_w: Optional[float] = None
    box_h: Optional[float] = None
    selected_player_id: Optional[int] = Field(default=None)
    action_type: Optional[str] = None
    action_phase: Optional[str] = None
    quality_rating: Optional[str] = None
    is_forced_action: Optional[bool] = None
    notes: Optional[str] = None
    status: Optional[AnnotationStatus] = None


class FrameAnnotationOut(BaseModel):
    id: int
    uuid: str
    task_batch_id: int
    frame_index: int
    annotator_id: int
    annotator_name: str
    keypoints: Optional[Any] = None
    box_x: Optional[float] = None
    box_y: Optional[float] = None
    box_w: Optional[float] = None
    box_h: Optional[float] = None
    selected_player_id: Optional[int] = None
    action_type: Optional[str] = None
    action_phase: Optional[str] = None
    quality_rating: Optional[str] = None
    is_forced_action: bool = False
    notes: Optional[str] = None
    is_ml_generated: bool
    status: AnnotationStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchAnnotationSubmit(BaseModel):
    """批量提交标注（一次提交多帧）"""
    annotations: List[FrameAnnotationCreate]


class ConfirmAnnotationsRequest(BaseModel):
    """确认标注请求"""
    task_batch_id: int
    frame_indices: Optional[List[int]] = None
