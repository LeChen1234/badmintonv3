from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.task_batch import TaskBatch, TaskStatus
from app.schemas.task_batch import TaskBatchCreate, TaskBatchUpdate, TaskBatchOut
from app.core.security import get_current_user
from app.core.permissions import require_roles
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["任务管理"])


def _enrich_batch(batch: TaskBatch) -> TaskBatchOut:
    return TaskBatchOut(
        id=batch.id,
        project_id=batch.project_id,
        name=batch.name,
        action_category=batch.action_category,
        assigned_to=batch.assigned_to,
        assignee_name=batch.assignee.display_name if batch.assignee else None,
        status=batch.status,
        frame_start=batch.frame_start,
        frame_end=batch.frame_end,
        total_frames=batch.total_frames,
        completed_frames=batch.completed_frames,
        deadline=batch.deadline,
        created_at=batch.created_at,
    )


@router.get("", response_model=List[TaskBatchOut])
def list_batches(
    project_id: Optional[int] = None,
    assigned_to: Optional[int] = None,
    task_status: Optional[TaskStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.STUDENT:
        assigned_to = current_user.id

    batches = task_service.list_task_batches(
        db, project_id=project_id, assigned_to=assigned_to,
        status=task_status, skip=skip, limit=limit,
    )
    return [_enrich_batch(b) for b in batches]


@router.post("/batch", response_model=TaskBatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    data: TaskBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    batch = task_service.create_task_batch(db, data, current_user)
    return _enrich_batch(batch)


@router.get("/{batch_id}", response_model=TaskBatchOut)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    return _enrich_batch(batch)


@router.put("/{batch_id}", response_model=TaskBatchOut)
def update_batch(
    batch_id: int,
    data: TaskBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    batch = task_service.update_task_batch(db, batch, data)
    return _enrich_batch(batch)


@router.post("/{batch_id}/assign", response_model=TaskBatchOut)
def assign_batch(
    batch_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    batch = task_service.assign_task(db, batch, user_id)
    return _enrich_batch(batch)


@router.post("/{batch_id}/trigger-ml")
async def trigger_ml(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    from app.services.ml_service import trigger_prediction
    from app.models.project import Project

    project = db.query(Project).filter(Project.id == batch.project_id).first()
    if not project or not project.ls_project_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "项目未关联 Label Studio")

    result = await trigger_prediction(project.ls_project_id)
    return result
