from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from app.models.annotation import AnnotationStatus


class KeypointData(BaseModel):
    name: str
    x: float
    y: float
    visibility: int = 2


class ContactPoint(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    visibility: int = 0


class ContactUV(BaseModel):
    u: Optional[float] = None
    v: Optional[float] = None


class ContactAnnotation(BaseModel):
    """Sparse contact-event geometry in image / face-parameter coordinates."""
    tolerance_flag: bool = False
    shuttle: Optional[ContactPoint] = None
    face_corners: Optional[List[KeypointData]] = None
    contact_point: Optional[ContactPoint] = None
    contact_uv: Optional[ContactUV] = None
    contact_zone: Optional[str] = None
    face_attitude: Optional[str] = None
    support_foot: Optional[str] = None
    error_attributes: Optional[List[str]] = None


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
    is_contact_event: bool = False
    contact: Optional[ContactAnnotation] = None
    is_ml_generated: bool = False
    assist_metadata: Optional[Dict[str, Any]] = None
    assist_accepted: bool = False
    annotation_duration_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)


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
    is_contact_event: Optional[bool] = None
    contact: Optional[ContactAnnotation] = None
    assist_metadata: Optional[Dict[str, Any]] = None
    assist_accepted: Optional[bool] = None
    annotation_duration_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)


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
    is_contact_event: bool = False
    contact: Optional[Any] = None
    is_ml_generated: bool
    taxonomy_version: Optional[str] = None
    assist_metadata: Optional[Any] = None
    assist_accepted: bool = False
    annotation_duration_ms: Optional[int] = None
    workflow_stage: str = "student_coarse"
    expert_review_required: bool = False
    expert_review_reasons: Optional[Any] = None
    expert_reviewed_by: Optional[int] = None
    expert_reviewed_at: Optional[datetime] = None
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
