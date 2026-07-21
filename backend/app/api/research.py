from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.core.security import get_current_user
from app.database import get_db
from app.models.active_learning_round import ActiveLearningRound
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.research import ActiveRoundCreate
from app.services.active_learning_service import evaluate_round
from app.services.research_release_service import load_research_protocol
from app.utils.audit import log_audit

router = APIRouter(prefix="/research", tags=["研究闭环"])


def _serialize(round_: ActiveLearningRound) -> dict:
    return {
        "id": round_.id, "project_id": round_.project_id, "round_index": round_.round_index,
        "dataset_id": round_.dataset_id, "model_version": round_.model_version,
        "selection_strategy": round_.selection_strategy, "annotation_count": round_.annotation_count,
        "annotation_hours": round_.annotation_hours, "metrics": round_.metrics,
        "component_gains": round_.component_gains, "marginal_utility": round_.marginal_utility,
        "recommended_weights": round_.recommended_weights, "stop_recommended": round_.stop_recommended,
        "created_at": round_.created_at.isoformat() if round_.created_at else None,
    }


@router.get("/{project_id}/rounds")
def list_rounds(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    rounds = db.query(ActiveLearningRound).filter(
        ActiveLearningRound.project_id == project_id
    ).order_by(ActiveLearningRound.round_index).all()
    protocol = load_research_protocol()["active_learning"]
    return {
        "project_id": project_id,
        "protocol": protocol,
        "rounds": [_serialize(round_) for round_ in rounds],
        "current_weights": rounds[-1].recommended_weights if rounds else protocol["initial_component_weights"],
        "stop_recommended": rounds[-1].stop_recommended if rounds else False,
    }


@router.post("/{project_id}/rounds", status_code=status.HTTP_201_CREATED)
def create_round(
    project_id: int,
    data: ActiveRoundCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT])(current_user)
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    prior = db.query(ActiveLearningRound).filter(
        ActiveLearningRound.project_id == project_id
    ).order_by(ActiveLearningRound.round_index).all()
    if any(round_.dataset_id == data.dataset_id for round_ in prior):
        raise HTTPException(status.HTTP_409_CONFLICT, "该数据集版本已登记，不能重复作为新一轮")
    metrics = {
        "macro_f1_mean": data.macro_f1_mean, "macro_f1_std": data.macro_f1_std,
        "repeat_count": data.repeat_count,
        "balanced_accuracy_mean": data.balanced_accuracy_mean,
        "nll_mean": data.nll_mean, "ece_mean": data.ece_mean,
        "statistical_comparison": data.statistical_comparison,
    }
    utility, weights, stop, decision = evaluate_round(prior, metrics, data.annotation_hours, data.component_gains)
    round_ = ActiveLearningRound(
        project_id=project_id, round_index=len(prior) + 1, dataset_id=data.dataset_id,
        model_version=data.model_version, selection_strategy=data.selection_strategy,
        annotation_count=data.annotation_count, annotation_hours=data.annotation_hours,
        metrics=metrics, component_gains=data.component_gains, marginal_utility=utility,
        recommended_weights=weights, stop_recommended=stop, created_by=current_user.id,
    )
    db.add(round_)
    db.commit()
    db.refresh(round_)
    log_audit(db, current_user.id, "create_active_learning_round", f"project_id={project_id}, round={round_.round_index}, stop={stop}")
    return {"round": _serialize(round_), "decision": decision}
