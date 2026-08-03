"""CRUD and review workflow for continuous action segments."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.annotation import AnnotationStatus
from app.models.batch_frame import BatchFrame
from app.models.player import Player
from app.models.task_batch import TaskBatch, TaskStatus
from app.models.temporal_segment import TemporalSegment
from app.models.user import User, UserRole
from app.schemas.temporal_segment import (
    TemporalSegmentConfirmRequest,
    TemporalSegmentCreate,
    TemporalSegmentOut,
    TemporalSegmentUpdate,
)
from app.services.taxonomy_service import load_annotation_taxonomy
from app.services.temporal_segment_service import (
    validate_segment_range,
    validate_segment_taxonomy,
)
from app.utils.audit import log_audit


router = APIRouter(prefix="/segments", tags=["连续片段标注"])


def _require_batch_access(batch: TaskBatch, user: User, *, writable: bool = False) -> None:
    if user.role == UserRole.STUDENT and user.id not in (
        batch.assigned_to,
        batch.secondary_assigned_to,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问其他标注员的任务")
    if writable and batch.status == TaskStatus.LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "任务已锁定，不能修改片段")


def _get_batch(db: Session, batch_id: int, user: User, *, writable: bool = False) -> TaskBatch:
    batch = db.query(TaskBatch).filter(TaskBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    _require_batch_access(batch, user, writable=writable)
    if writable and not batch.metadata_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先确认任务元信息")
    return batch


def _validate_payload(
    db: Session,
    batch: TaskBatch,
    user: User,
    selected_player_id: int,
    start_frame: int,
    end_frame: int,
    action_type: str,
    action_phase: Optional[str],
    *,
    exclude_id: Optional[int] = None,
) -> tuple[int, int]:
    try:
        validate_segment_range(start_frame, end_frame, batch.total_frames)
        validate_segment_taxonomy(action_type, action_phase, load_annotation_taxonomy())
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    player = db.query(Player).filter(
        Player.id == selected_player_id,
        Player.task_batch_id == batch.id,
    ).first()
    if not player:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选人物不在当前任务中")

    frame_rows = (
        db.query(BatchFrame)
        .filter(
            BatchFrame.task_batch_id == batch.id,
            BatchFrame.frame_index.in_([start_frame, end_frame]),
        )
        .all()
    )
    timestamps = {row.frame_index: int(row.timestamp_ms or 0) for row in frame_rows}
    if start_frame not in timestamps or end_frame not in timestamps:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "片段起止帧不存在")

    conflict = db.query(TemporalSegment).filter(
        TemporalSegment.task_batch_id == batch.id,
        TemporalSegment.selected_player_id == selected_player_id,
        TemporalSegment.annotator_id == user.id,
        TemporalSegment.start_frame <= end_frame,
        TemporalSegment.end_frame >= start_frame,
    )
    if exclude_id is not None:
        conflict = conflict.filter(TemporalSegment.id != exclude_id)
    if conflict.first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "该人物已有与此范围重叠的动作片段；请调整边界或编辑原片段",
        )
    return timestamps[start_frame], timestamps[end_frame]


@router.get("", response_model=List[TemporalSegmentOut])
def list_segments(
    task_batch_id: int,
    selected_player_id: Optional[int] = None,
    segment_status: Optional[AnnotationStatus] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = _get_batch(db, task_batch_id, current_user)
    query = db.query(TemporalSegment).filter(TemporalSegment.task_batch_id == batch.id)
    if current_user.role == UserRole.STUDENT:
        query = query.filter(TemporalSegment.annotator_id == current_user.id)
    if selected_player_id is not None:
        query = query.filter(TemporalSegment.selected_player_id == selected_player_id)
    if segment_status is not None:
        query = query.filter(TemporalSegment.status == segment_status.value)
    return query.order_by(TemporalSegment.start_frame, TemporalSegment.id).all()


@router.post("", response_model=TemporalSegmentOut, status_code=status.HTTP_201_CREATED)
def create_segment(
    data: TemporalSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = _get_batch(db, data.task_batch_id, current_user, writable=True)
    phase = None if current_user.role == UserRole.STUDENT else data.action_phase
    start_ms, end_ms = _validate_payload(
        db,
        batch,
        current_user,
        data.selected_player_id,
        data.start_frame,
        data.end_frame,
        data.action_type,
        phase,
    )
    segment = TemporalSegment(
        task_batch_id=batch.id,
        selected_player_id=data.selected_player_id,
        annotator_id=current_user.id,
        annotator_name=current_user.display_name,
        start_frame=data.start_frame,
        end_frame=data.end_frame,
        start_timestamp_ms=start_ms,
        end_timestamp_ms=end_ms,
        action_type=data.action_type,
        action_phase=phase,
        context=data.context.model_dump() if data.context else None,
        execution=data.execution.model_dump() if data.execution else None,
        outcome=data.outcome.model_dump() if data.outcome else None,
        evidence=data.evidence.model_dump() if data.evidence else None,
        notes=data.notes,
        status=AnnotationStatus.DRAFT.value,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    log_audit(db, current_user.id, "create_temporal_segment", f"segment_id={segment.id}, batch_id={batch.id}")
    return segment


@router.post("/submit", response_model=List[TemporalSegmentOut])
def submit_segments(
    task_batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = _get_batch(db, task_batch_id, current_user, writable=True)
    query = db.query(TemporalSegment).filter(
        TemporalSegment.task_batch_id == batch.id,
        TemporalSegment.annotator_id == current_user.id,
        TemporalSegment.status == AnnotationStatus.DRAFT.value,
    )
    segments = query.all()
    if not segments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "没有可提交的片段")
    for segment in segments:
        segment.status = AnnotationStatus.SUBMITTED.value
    db.commit()
    for segment in segments:
        db.refresh(segment)
    log_audit(db, current_user.id, "submit_temporal_segments", f"batch_id={batch.id}, count={len(segments)}")
    return segments


@router.post("/confirm", response_model=List[TemporalSegmentOut])
def confirm_segments(
    data: TemporalSegmentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.SUPER_ADMIN,
        UserRole.ADMIN,
        UserRole.LEADER,
        UserRole.EXPERT,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅管理员、组长或专家可确认片段")
    segments = db.query(TemporalSegment).filter(TemporalSegment.id.in_(data.segment_ids)).all()
    if len(segments) != len(set(data.segment_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "部分片段不存在")
    for segment in segments:
        if segment.status != AnnotationStatus.SUBMITTED.value:
            raise HTTPException(status.HTTP_409_CONFLICT, f"片段 {segment.id} 尚未提交")
        segment.status = AnnotationStatus.CONFIRMED.value
        segment.confirmed_by = current_user.id
        segment.confirmed_at = datetime.utcnow()
    db.commit()
    for segment in segments:
        db.refresh(segment)
    log_audit(db, current_user.id, "confirm_temporal_segments", f"count={len(segments)}")
    return segments


@router.put("/{segment_id}", response_model=TemporalSegmentOut)
def update_segment(
    segment_id: int,
    data: TemporalSegmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(TemporalSegment).filter(TemporalSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "片段不存在")
    batch = _get_batch(db, segment.task_batch_id, current_user, writable=True)
    if segment.status == AnnotationStatus.CONFIRMED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "已确认片段不能修改")
    if current_user.role == UserRole.STUDENT and segment.annotator_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "不能修改其他人的片段")

    update = data.model_dump(exclude_unset=True)
    for field in ("context", "execution", "outcome", "evidence"):
        value = getattr(data, field)
        if field in update and value is not None:
            update[field] = value.model_dump()
    selected_player_id = int(update.get("selected_player_id", segment.selected_player_id))
    start_frame = int(update.get("start_frame", segment.start_frame))
    end_frame = int(update.get("end_frame", segment.end_frame))
    action_type = str(update.get("action_type", segment.action_type))
    action_phase = update.get("action_phase", segment.action_phase)
    if current_user.role == UserRole.STUDENT:
        action_phase = None
        update.pop("action_phase", None)
    start_ms, end_ms = _validate_payload(
        db,
        batch,
        current_user,
        selected_player_id,
        start_frame,
        end_frame,
        action_type,
        action_phase,
        exclude_id=segment.id,
    )
    update.update(
        selected_player_id=selected_player_id,
        start_frame=start_frame,
        end_frame=end_frame,
        start_timestamp_ms=start_ms,
        end_timestamp_ms=end_ms,
        action_type=action_type,
        action_phase=action_phase,
        status=AnnotationStatus.DRAFT.value,
        confirmed_by=None,
        confirmed_at=None,
    )
    for key, value in update.items():
        setattr(segment, key, value)
    db.commit()
    db.refresh(segment)
    log_audit(db, current_user.id, "update_temporal_segment", f"segment_id={segment.id}")
    return segment


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(TemporalSegment).filter(TemporalSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "片段不存在")
    _get_batch(db, segment.task_batch_id, current_user, writable=True)
    if segment.status == AnnotationStatus.CONFIRMED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "已确认片段不能删除")
    if current_user.role == UserRole.STUDENT and segment.annotator_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "不能删除其他人的片段")
    db.delete(segment)
    db.commit()
    log_audit(db, current_user.id, "delete_temporal_segment", f"segment_id={segment_id}")
