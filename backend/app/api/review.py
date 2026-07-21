from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.task_batch import TaskBatch, TaskStatus
from app.models.annotation import FrameAnnotation, AnnotationStatus
from app.models.annotation_revision import AnnotationRevision
from app.models.adjudication_record import AdjudicationRecord
from app.schemas.review import ReviewSubmit, ReviewAction, ReviewRecordOut, AdjudicationRequest
from app.core.security import get_current_user
from app.core.permissions import require_roles
from app.services import review_service
from app.services.agreement_service import build_agreement_report
from app.services.research_release_service import load_research_protocol
from app.utils.audit import log_audit
from app.services import task_service

router = APIRouter(prefix="/review", tags=["审核流程"])


@router.get("/expert-queue")
def expert_judgment_queue(
    task_batch_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return only records requiring domain judgment; coarse geometry is context, not rework."""
    require_roles([UserRole.EXPERT, UserRole.ADMIN])(current_user)
    query = db.query(FrameAnnotation).filter(
        FrameAnnotation.expert_review_required.is_(True),
        FrameAnnotation.workflow_stage == "expert_pending",
        FrameAnnotation.status != AnnotationStatus.REJECTED,
    )
    if task_batch_id is not None:
        query = query.filter(FrameAnnotation.task_batch_id == task_batch_id)
    rows = query.order_by(FrameAnnotation.task_batch_id, FrameAnnotation.frame_index).all()
    return {
        "pending_count": len(rows),
        "expert_fields": [
            "action_phase", "quality_rating", "is_forced_action",
            "contact.contact_zone", "contact.face_attitude", "contact.support_foot", "contact.error_attributes",
        ],
        "items": [
            {
                "annotation_id": row.id,
                "task_batch_id": row.task_batch_id,
                "task_batch_name": row.task_batch.name if row.task_batch else "",
                "frame_index": row.frame_index,
                "player_id": row.selected_player_id,
                "player_name": row.selected_player_obj.name if row.selected_player_obj else "",
                "coarse_context": {
                    "bbox": [row.box_x, row.box_y, row.box_w, row.box_h],
                    "visible_keypoints": sum(
                        int(point.get("visibility", 0)) > 0 for point in (row.keypoints or []) if isinstance(point, dict)
                    ),
                    "action_type": row.action_type,
                    "is_contact_event": row.is_contact_event,
                },
                "reasons": row.expert_review_reasons or [],
            }
            for row in rows
        ],
    }


def _candidate_groups(db: Session, task_id: int):
    annotations = (
        db.query(FrameAnnotation)
        .filter(
            FrameAnnotation.task_batch_id == task_id,
            FrameAnnotation.status != AnnotationStatus.REJECTED,
        )
        .order_by(FrameAnnotation.frame_index, FrameAnnotation.annotator_id)
        .all()
    )
    groups = {}
    for annotation in annotations:
        groups.setdefault((annotation.frame_index, annotation.selected_player_id), []).append(annotation)
    resolved = {
        (record.frame_index, record.selected_player_id)
        for record in db.query(AdjudicationRecord).filter(AdjudicationRecord.task_batch_id == task_id).all()
    }
    return {
        key: values for key, values in groups.items()
        if len({annotation.annotator_id for annotation in values}) >= 2 and key not in resolved
    }


@router.post("/{task_id}/submit")
def submit_review(
    task_id: int,
    data: ReviewSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    if batch.status == TaskStatus.ANNOTATING and batch.secondary_assigned_to:
        expected = {batch.assigned_to, batch.secondary_assigned_to}
        rows = db.query(FrameAnnotation).filter(FrameAnnotation.task_batch_id == task_id).all()
        submitted_by = {annotation.annotator_id for annotation in rows if annotation.status == AnnotationStatus.SUBMITTED}
        has_drafts = any(annotation.status == AnnotationStatus.DRAFT and annotation.annotator_id in expected for annotation in rows)
        if not expected.issubset(submitted_by) or has_drafts:
            raise HTTPException(status.HTTP_409_CONFLICT, "主标注员与独立复标员都提交后才能进入审核")
    batch = review_service.submit_for_review(db, batch, current_user, data.comment)
    log_audit(db, current_user.id, "submit_review", f"task_id={task_id}, status={batch.status.value}")
    return {"status": batch.status.value, "message": "提交成功"}


@router.post("/{task_id}/approve")
def approve_review(
    task_id: int,
    data: ReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    if batch.status == TaskStatus.EXPERT_REVIEW and _candidate_groups(db, task_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "仍有盲法复标分歧未完成专家裁决")
    if batch.status == TaskStatus.EXPERT_REVIEW:
        pending_judgments = db.query(FrameAnnotation).filter(
            FrameAnnotation.task_batch_id == task_id,
            FrameAnnotation.expert_review_required.is_(True),
            FrameAnnotation.workflow_stage == "expert_pending",
        ).count()
        if pending_judgments:
            raise HTTPException(status.HTTP_409_CONFLICT, f"仍有 {pending_judgments} 条专业判定未完成")
    batch = review_service.approve(db, batch, current_user, data.comment)
    log_audit(db, current_user.id, "approve_review", f"task_id={task_id}")
    return {"status": batch.status.value, "message": "审核通过"}


@router.post("/{task_id}/reject")
def reject_review(
    task_id: int,
    data: ReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    batch = review_service.reject(db, batch, current_user, data.comment)
    log_audit(db, current_user.id, "reject_review", f"task_id={task_id}, comment={data.comment or ''}")
    return {"status": batch.status.value, "message": "已打回"}


@router.get("/{task_id}/history", response_model=List[ReviewRecordOut])
def review_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = review_service.get_review_history(db, task_id)
    result = []
    for r in records:
        result.append(ReviewRecordOut(
            id=r.id,
            task_batch_id=r.task_batch_id,
            reviewer_id=r.reviewer_id,
            reviewer_name=r.reviewer.display_name if r.reviewer else None,
            review_level=r.review_level,
            result=r.result,
            comment=r.comment,
            created_at=r.created_at,
        ))
    return result


@router.get("/{task_id}/agreement")
def annotation_agreement(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Research-only agreement report; annotators cannot inspect peers' labels."""
    require_roles([UserRole.LEADER, UserRole.EXPERT, UserRole.ADMIN])(current_user)
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    annotations = (
        db.query(FrameAnnotation)
        .filter(FrameAnnotation.task_batch_id == task_id)
        .order_by(FrameAnnotation.frame_index, FrameAnnotation.annotator_id)
        .all()
    )
    protocol = load_research_protocol().get("agreement", {})
    report = build_agreement_report(
        annotations,
        pck_thresholds=tuple(protocol.get("pck_thresholds", [0.05, 0.10])),
        minimum_items=int(protocol.get("minimum_double_annotated_items", 20)),
    )
    report["task_batch_id"] = task_id
    report["match_uuid"] = batch.match_uuid
    return report


@router.get("/{task_id}/disagreements")
def list_disagreements(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.LEADER, UserRole.EXPERT, UserRole.ADMIN])(current_user)
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    result = []
    for (frame_index, player_id), candidates in _candidate_groups(db, task_id).items():
        metrics = build_agreement_report(candidates, minimum_items=1)
        result.append({
            "frame_index": frame_index,
            "selected_player_id": player_id,
            "candidate_count": len(candidates),
            "metrics": metrics,
            "candidates": [
                {
                    "annotation_id": annotation.id,
                    "option": chr(65 + index),
                    "action_type": annotation.action_type,
                    "action_phase": annotation.action_phase,
                    "quality_rating": annotation.quality_rating,
                    "is_contact_event": annotation.is_contact_event,
                    "keypoints": annotation.keypoints,
                    "bbox": [annotation.box_x, annotation.box_y, annotation.box_w, annotation.box_h],
                    "status": annotation.status.value,
                }
                for index, annotation in enumerate(candidates)
            ],
        })
    result.sort(key=lambda item: (
        item["metrics"]["categorical"]["action_type"]["observed_agreement"] == 1.0,
        -(item["metrics"]["keypoints"]["mean_normalized_error"] or 0.0),
    ))
    return {"task_batch_id": task_id, "unresolved_count": len(result), "items": result}


@router.post("/{task_id}/adjudicate")
def adjudicate_annotation(
    task_id: int,
    data: AdjudicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.EXPERT, UserRole.ADMIN])(current_user)
    batch = db.query(TaskBatch).filter(TaskBatch.id == task_id).first()
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if batch.status != TaskStatus.EXPERT_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, "仅专家终审阶段允许生成 gold annotation")
    winner = db.query(FrameAnnotation).filter(
        FrameAnnotation.id == data.winner_annotation_id,
        FrameAnnotation.task_batch_id == task_id,
    ).first()
    if not winner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "候选标注不存在")
    key = (winner.frame_index, winner.selected_player_id)
    candidates = _candidate_groups(db, task_id).get(key)
    if not candidates or winner.id not in {candidate.id for candidate in candidates}:
        raise HTTPException(status.HTTP_409_CONFLICT, "该帧不存在待裁决的独立复标候选")
    allowed = {
        "selected_player_id", "keypoints", "box_x", "box_y", "box_w", "box_h",
        "action_type", "action_phase", "quality_rating", "is_forced_action", "notes",
        "is_contact_event", "contact",
    }
    unknown = set(data.overrides) - allowed
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"裁决覆盖字段不允许: {sorted(unknown)}")
    snapshot_fields = sorted(allowed)
    before = {field: getattr(winner, field) for field in snapshot_fields}
    for field, value in data.overrides.items():
        setattr(winner, field, value)
    after = {field: getattr(winner, field) for field in snapshot_fields}
    changed = [field for field in snapshot_fields if before[field] != after[field]]
    if changed:
        db.add(AnnotationRevision(
            annotation_id=winner.id, editor_id=current_user.id, source="expert_adjudication",
            changed_fields=changed, before_snapshot=before, after_snapshot=after,
        ))
    for candidate in candidates:
        candidate.status = AnnotationStatus.CONFIRMED if candidate.id == winner.id else AnnotationStatus.REJECTED
    disagreement = build_agreement_report(candidates, minimum_items=1)
    record = AdjudicationRecord(
        task_batch_id=task_id,
        frame_index=winner.frame_index,
        selected_player_id=winner.selected_player_id,
        expert_id=current_user.id,
        winner_annotation_id=winner.id,
        candidate_annotation_ids=[candidate.id for candidate in candidates],
        disagreement_snapshot=disagreement,
        comment=data.comment,
    )
    db.add(record)
    db.commit()
    task_service.sync_batch_completed_frames(db, task_id)
    log_audit(db, current_user.id, "adjudicate_annotation", f"task_id={task_id}, frame={winner.frame_index}, winner={winner.id}")
    return {"adjudication_id": record.id, "winner_annotation_id": winner.id, "status": "confirmed"}
