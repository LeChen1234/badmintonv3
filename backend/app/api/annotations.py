from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.models.annotation import FrameAnnotation, AnnotationStatus
from app.models.task_batch import TaskBatch, TaskStatus
from app.models.player import Player
from app.models.annotation_revision import AnnotationRevision
from app.schemas.annotation import (
    FrameAnnotationCreate,
    FrameAnnotationUpdate,
    FrameAnnotationOut,
    BatchAnnotationSubmit,
    ConfirmAnnotationsRequest,
)
from app.core.security import get_current_user
from app.core.permissions import require_roles, require_super_admin
from app.services import task_service
from app.utils.audit import log_audit
from app.services.taxonomy_service import load_annotation_taxonomy

router = APIRouter(prefix="/annotations", tags=["标注管理"])


REVISION_FIELDS = (
    "selected_player_id", "keypoints", "box_x", "box_y", "box_w", "box_h",
    "action_type", "action_phase", "quality_rating", "is_forced_action", "notes",
    "is_contact_event", "contact", "assist_accepted",
)


def _annotation_snapshot(annotation: FrameAnnotation) -> dict:
    return {field: getattr(annotation, field) for field in REVISION_FIELDS}


def _player_map(batch: TaskBatch) -> dict:
    return {p.id: p for p in (batch.players or [])}


def _require_batch_access(batch: TaskBatch, user: User, *, writable: bool = False) -> None:
    if user.role == UserRole.STUDENT and user.id not in (batch.assigned_to, batch.secondary_assigned_to):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问其他标注员的任务")
    if writable and batch.status == TaskStatus.LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "任务已锁定，不能修改标注")


def _validate_taxonomy(action_type: str, action_phase: Optional[str], quality_rating: Optional[str]) -> None:
    taxonomy = load_annotation_taxonomy()
    checks = (
        ("动作类型", action_type, taxonomy["actions"]),
        ("动作阶段", action_phase, taxonomy["phases"]),
        ("动作质量", quality_rating, taxonomy["qualities"]),
    )
    for label, value, options in checks:
        if value is not None and value not in {item["value"] for item in options}:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label}不在当前标注规范中: {value}")


def _expert_triage(assist_metadata, keypoints, is_contact_event: bool) -> list[str]:
    reasons = ["动作阶段、动作质量与技术属性需要体育专家判定"]
    if isinstance(assist_metadata, dict) and float(assist_metadata.get("review_priority") or 0) >= 0.65:
        reasons.append("预标注质量评估低于直接采用阈值")
    visible = sum(int(point.get("visibility", 0)) > 0 for point in (keypoints or []) if isinstance(point, dict))
    if visible < 15:
        reasons.append(f"人体关键点可见数量不足（{visible}/23）")
    if is_contact_event:
        reasons.append("击球接触与拍面技术属性需要专家复核")
    return reasons


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
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    _require_batch_access(batch, current_user)
    q = db.query(FrameAnnotation).filter(FrameAnnotation.task_batch_id == task_batch_id)
    if current_user.role == UserRole.STUDENT:
        q = q.filter(FrameAnnotation.annotator_id == current_user.id)
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
    _require_batch_access(batch, current_user, writable=True)
    if not batch.metadata_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先完成任务元信息填写并确认，再开始标注")
    if data.selected_player_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择选手")
    if any(value is None for value in (data.box_x, data.box_y, data.box_w, data.box_h)) or data.box_w <= 0 or data.box_h <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先为该人员绘制有效边界框")
    if not (data.action_type or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择动作类型")
    _validate_taxonomy(data.action_type, data.action_phase, data.quality_rating)

    player_map = _player_map(batch)
    if data.selected_player_id not in player_map:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选选手不在当前任务元信息中")
    duplicate = db.query(FrameAnnotation).filter(
        FrameAnnotation.task_batch_id == data.task_batch_id,
        FrameAnnotation.frame_index == data.frame_index,
        FrameAnnotation.annotator_id == current_user.id,
        FrameAnnotation.selected_player_id == data.selected_player_id,
    ).first()
    if duplicate:
        raise HTTPException(status.HTTP_409_CONFLICT, "该帧中该人员已有标注记录，请编辑现有记录")

    keypoints_dict = None
    if data.keypoints:
        keypoints_dict = [kp.model_dump() for kp in data.keypoints]

    contact_dict = data.contact.model_dump() if data.contact else None
    is_student = current_user.role == UserRole.STUDENT
    expert_reasons = _expert_triage(data.assist_metadata, keypoints_dict, data.is_contact_event) if is_student else []

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
        action_phase=None if is_student else data.action_phase,
        quality_rating=None if is_student else data.quality_rating,
        is_forced_action=False if is_student else data.is_forced_action,
        notes=data.notes,
        is_contact_event=data.is_contact_event,
        contact=contact_dict,
        is_ml_generated=data.is_ml_generated,
        taxonomy_version=str(load_annotation_taxonomy().get("version", "unknown")),
        assist_metadata=data.assist_metadata,
        assist_accepted=data.assist_accepted,
        annotation_duration_ms=data.annotation_duration_ms,
        workflow_stage="expert_pending" if is_student else "expert_completed",
        expert_review_required=is_student,
        expert_review_reasons=expert_reasons or None,
        expert_reviewed_by=None if is_student else current_user.id,
        expert_reviewed_at=None if is_student else datetime.utcnow(),
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
        _require_batch_access(batch, current_user, writable=True)
        if not batch.metadata_confirmed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先完成任务元信息填写并确认，再开始标注")
        if item.selected_player_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择选手")
        if not (item.action_type or "").strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择动作类型")
        _validate_taxonomy(item.action_type, item.action_phase, item.quality_rating)
        player_map = _player_map(batch)
        if item.selected_player_id not in player_map:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选选手不在当前任务元信息中")

        keypoints_dict = None
        if item.keypoints:
            keypoints_dict = [kp.model_dump() for kp in item.keypoints]

        contact_dict = item.contact.model_dump() if item.contact else None
        is_student = current_user.role == UserRole.STUDENT
        expert_reasons = _expert_triage(item.assist_metadata, keypoints_dict, item.is_contact_event) if is_student else []

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
            action_phase=None if is_student else item.action_phase,
            quality_rating=None if is_student else item.quality_rating,
            is_forced_action=False if is_student else item.is_forced_action,
            notes=item.notes,
            is_contact_event=item.is_contact_event,
            contact=contact_dict,
            is_ml_generated=item.is_ml_generated,
            taxonomy_version=str(load_annotation_taxonomy().get("version", "unknown")),
            assist_metadata=item.assist_metadata,
            assist_accepted=item.assist_accepted,
            annotation_duration_ms=item.annotation_duration_ms,
            workflow_stage="expert_pending" if is_student else "expert_completed",
            expert_review_required=is_student,
            expert_review_reasons=expert_reasons or None,
            expert_reviewed_by=None if is_student else current_user.id,
            expert_reviewed_at=None if is_student else datetime.utcnow(),
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
    _require_batch_access(batch, current_user, writable=True)
    if not batch.metadata_confirmed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先完成任务元信息填写并确认，再开始标注")

    if annotation.status == AnnotationStatus.CONFIRMED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已确认的标注不能修改")

    update_data = data.model_dump(exclude_unset=True)
    if "keypoints" in update_data and update_data["keypoints"] is not None:
        update_data["keypoints"] = [kp.model_dump() for kp in data.keypoints]
    if "contact" in update_data and update_data["contact"] is not None:
        update_data["contact"] = data.contact.model_dump() if data.contact else None

    # Preserve the student author; expert identity is stored separately and in revisions.
    update_data["taxonomy_version"] = str(load_annotation_taxonomy().get("version", "unknown"))
    if current_user.role == UserRole.STUDENT:
        for specialist_field in ("action_phase", "quality_rating", "is_forced_action"):
            update_data.pop(specialist_field, None)
        update_data["workflow_stage"] = "expert_pending"
        update_data["expert_review_required"] = True
        update_data["expert_review_reasons"] = _expert_triage(
            update_data.get("assist_metadata", annotation.assist_metadata),
            update_data.get("keypoints", annotation.keypoints),
            bool(update_data.get("is_contact_event", annotation.is_contact_event)),
        )
    elif current_user.role in (UserRole.EXPERT, UserRole.ADMIN):
        update_data["workflow_stage"] = "expert_completed"
        update_data["expert_review_required"] = False
        update_data["expert_reviewed_by"] = current_user.id
        update_data["expert_reviewed_at"] = datetime.utcnow()

    next_selected_player_id = update_data.get("selected_player_id") if "selected_player_id" in update_data else annotation.selected_player_id
    next_action_type = (update_data.get("action_type") if "action_type" in update_data else annotation.action_type) or ""
    if next_selected_player_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择选手")
    if not str(next_action_type).strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择动作类型")
    next_action_phase = update_data.get("action_phase") if "action_phase" in update_data else annotation.action_phase
    next_quality_rating = update_data.get("quality_rating") if "quality_rating" in update_data else annotation.quality_rating
    # 学生只能维护粗标字段。历史专家字段即使来自旧版规范，也不应阻塞学生继续
    # 修正人物框、人体点或击球接触几何；专家值会在上方被完整保留。
    if current_user.role == UserRole.STUDENT:
        _validate_taxonomy(str(next_action_type), None, None)
    else:
        _validate_taxonomy(str(next_action_type), next_action_phase, next_quality_rating)
    player_map = _player_map(batch)
    if next_selected_player_id not in player_map:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "所选选手不在当前任务元信息中")

    before_snapshot = _annotation_snapshot(annotation)
    for key, value in update_data.items():
        setattr(annotation, key, value)

    after_snapshot = _annotation_snapshot(annotation)
    changed_fields = [field for field in REVISION_FIELDS if before_snapshot[field] != after_snapshot[field]]
    if changed_fields:
        source = "assist_acceptance" if "assist_accepted" in changed_fields and annotation.assist_accepted else "manual_edit"
        db.add(AnnotationRevision(
            annotation_id=annotation.id,
            editor_id=current_user.id,
            source=source,
            changed_fields=changed_fields,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        ))

    db.commit()
    db.refresh(annotation)
    return annotation


@router.delete("/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
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
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    _require_batch_access(batch, current_user, writable=True)
    annotations = (
        db.query(FrameAnnotation)
        .filter(
            FrameAnnotation.task_batch_id == task_batch_id,
            FrameAnnotation.status == AnnotationStatus.DRAFT,
        )
        .all()
    )
    if current_user.role == UserRole.STUDENT:
        annotations = [annotation for annotation in annotations if annotation.annotator_id == current_user.id]
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
    grouped_annotators = {}
    for annotation in annotations:
        key = (annotation.frame_index, annotation.selected_player_id)
        grouped_annotators.setdefault(key, set()).add(annotation.annotator_id)
    if any(len(annotators) > 1 for annotators in grouped_annotators.values()):
        raise HTTPException(status.HTTP_409_CONFLICT, "独立复标候选必须经过专家裁决，不能批量全部确认")

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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模型预标注服务未启用，请在配置中设置 ENABLE_ML_BACKEND=true")

    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)

    batch = db.query(TaskBatch).filter(TaskBatch.id == task_batch_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    from app.services.ml_service import trigger_prediction
    result = await trigger_prediction(batch.project_id)
    return result
