from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.models.annotation import FrameAnnotation, AnnotationStatus
from app.models.task_batch import TaskBatch
from app.models.player import Player
from app.schemas.annotation import (
    FrameAnnotationCreate,
    FrameAnnotationUpdate,
    FrameAnnotationOut,
    BatchAnnotationSubmit,
    ConfirmAnnotationsRequest,
)
from app.core.security import get_current_user
from app.core.permissions import require_roles
from app.services import task_service
from app.utils.audit import log_audit

router = APIRouter(prefix="/annotations", tags=["标注管理"])


def _player_map(batch: TaskBatch) -> dict:
    return {p.id: p for p in (batch.players or [])}


@router.get("", response_model=List[FrameAnnotationOut])
def list_annotations(
    task_batch_id: int,
    frame_index: Optional[int] = None,
    annotation_status: Optional[AnnotationStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(FrameAnnotation).filter(FrameAnnotation.task_batch_id == task_batch_id)
    if frame_index is not None:
        q = q.filter(FrameAnnotation.frame_index == frame_index)
    if annotation_status:
        q = q.filter(FrameAnnotation.status == annotation_status)
    return q.order_by(FrameAnnotation.frame_index).offset(skip).limit(limit).all()


@router.post("", response_model=FrameAnnotationOut, status_code=status.HTTP_201_CREATED)
def create_annotation(
    data: FrameAnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == data.task_batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not batch.metadata_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先完成任务元信息填写并确认，再开始标注")
    if data.selected_player_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择选手")
    if not (data.action_type or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择动作类型")

    player_map = _player_map(batch)
    if data.selected_player_id not in player_map:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选选手不在当前任务元信息中")

    keypoints_dict = None
    if data.keypoints:
        keypoints_dict = [kp.model_dump() for kp in data.keypoints]

    annotation = FrameAnnotation(
        task_batch_id=data.task_batch_id,
        frame_index=data.frame_index,
        annotator_id=current_user.id,
        annotator_name=current_user.display_name,
        selected_player_id=data.selected_player_id,
        keypoints=keypoints_dict,
        box_x=data.box_x,
        box_y=data.box_y,
        box_w=data.box_w,
        box_h=data.box_h,
        action_type=data.action_type,
        action_phase=data.action_phase,
        quality_rating=data.quality_rating,
        is_forced_action=data.is_forced_action,
        notes=data.notes,
        is_ml_generated=data.is_ml_generated,
        status=AnnotationStatus.DRAFT,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


@router.post("/batch", response_model=List[FrameAnnotationOut], status_code=status.HTTP_201_CREATED)
def batch_create_annotations(
    data: BatchAnnotationSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = []
    for item in data.annotations:
        batch = db.query(TaskBatch).filter(TaskBatch.id == item.task_batch_id).first()
        if not batch:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
        if not batch.metadata_confirmed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先完成任务元信息填写并确认，再开始标注")
        if item.selected_player_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择选手")
        if not (item.action_type or "").strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择动作类型")
        player_map = _player_map(batch)
        if item.selected_player_id not in player_map:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选选手不在当前任务元信息中")

        keypoints_dict = None
        if item.keypoints:
            keypoints_dict = [kp.model_dump() for kp in item.keypoints]

        annotation = FrameAnnotation(
            task_batch_id=item.task_batch_id,
            frame_index=item.frame_index,
            annotator_id=current_user.id,
            annotator_name=current_user.display_name,
            selected_player_id=item.selected_player_id,
            keypoints=keypoints_dict,
            box_x=item.box_x,
            box_y=item.box_y,
            box_w=item.box_w,
            box_h=item.box_h,
            action_type=item.action_type,
            action_phase=item.action_phase,
            quality_rating=item.quality_rating,
            is_forced_action=item.is_forced_action,
            notes=item.notes,
            is_ml_generated=item.is_ml_generated,
            status=AnnotationStatus.DRAFT,
        )
        db.add(annotation)
        results.append(annotation)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


@router.put("/{annotation_id}", response_model=FrameAnnotationOut)
def update_annotation(
    annotation_id: int,
    data: FrameAnnotationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotation = db.query(FrameAnnotation).filter(FrameAnnotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "标注不存在")

    batch = db.query(TaskBatch).filter(TaskBatch.id == annotation.task_batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not batch.metadata_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先完成任务元信息填写并确认，再开始标注")

    if annotation.status == AnnotationStatus.CONFIRMED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已确认的标注不能修改")

    update_data = data.model_dump(exclude_unset=True)
    if "keypoints" in update_data and update_data["keypoints"] is not None:
        update_data["keypoints"] = [kp.model_dump() for kp in data.keypoints]

    update_data["annotator_id"] = current_user.id
    update_data["annotator_name"] = current_user.display_name

    next_selected_player_id = update_data.get("selected_player_id") if "selected_player_id" in update_data else annotation.selected_player_id
    next_action_type = (update_data.get("action_type") if "action_type" in update_data else annotation.action_type) or ""
    if next_selected_player_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择选手")
    if not str(next_action_type).strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择动作类型")
    player_map = _player_map(batch)
    if next_selected_player_id not in player_map:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选选手不在当前任务元信息中")

    for key, value in update_data.items():
        setattr(annotation, key, value)

    db.commit()
    db.refresh(annotation)
    return annotation


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotation = db.query(FrameAnnotation).filter(FrameAnnotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "标注不存在")
    if annotation.status == AnnotationStatus.CONFIRMED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已确认的标注不能删除")

    db.delete(annotation)
    db.commit()


@router.post("/submit", response_model=List[FrameAnnotationOut])
def submit_annotations(
    task_batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotations = (
        db.query(FrameAnnotation)
        .filter(
            FrameAnnotation.task_batch_id == task_batch_id,
            FrameAnnotation.status == AnnotationStatus.DRAFT,
        )
        .all()
    )
    if not annotations:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有可提交的草稿标注")

    for ann in annotations:
        ann.status = AnnotationStatus.SUBMITTED

    db.commit()
    for ann in annotations:
        db.refresh(ann)
    return annotations


@router.post("/confirm", response_model=List[FrameAnnotationOut])
def confirm_annotations(
    req: ConfirmAnnotationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)

    q = db.query(FrameAnnotation).filter(
        FrameAnnotation.task_batch_id == req.task_batch_id,
        FrameAnnotation.status == AnnotationStatus.SUBMITTED,
    )
    if req.frame_indices:
        q = q.filter(FrameAnnotation.frame_index.in_(req.frame_indices))

    annotations = q.all()
    if not annotations:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有可确认的标注")

    for ann in annotations:
        ann.status = AnnotationStatus.CONFIRMED
    db.commit()
    task_service.sync_batch_completed_frames(db, req.task_batch_id)
    log_audit(db, current_user.id, "confirm_annotations", f"task_batch_id={req.task_batch_id}, count={len(annotations)}")
    for ann in annotations:
        db.refresh(ann)
    return annotations


@router.post("/trigger-ml/{task_batch_id}")
async def trigger_ml_annotation(
    task_batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.ENABLE_ML_BACKEND:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "大模型标注功能未启用，请在配置中设置 ENABLE_ML_BACKEND=true")

    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)

    batch = db.query(TaskBatch).filter(TaskBatch.id == task_batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    from app.services.ml_service import trigger_prediction
    result = await trigger_prediction(batch.project_id)
    return result
