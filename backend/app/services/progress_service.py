"""Progress monitoring service."""

from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task_batch import TaskBatch, TaskStatus
from app.models.user import User
from app.schemas.progress import ProgressOverview, ProjectProgress, UserProgress


def get_overview(db: Session) -> ProgressOverview:
    projects = db.query(Project).all()
    project_progresses: List[ProjectProgress] = []

    total_batches_all = 0
    total_locked_all = 0

    for proj in projects:
        batches = db.query(TaskBatch).filter(TaskBatch.project_id == proj.id).all()
        total = len(batches)
        pending = sum(1 for b in batches if b.status == TaskStatus.PENDING)
        annotating = sum(1 for b in batches if b.status == TaskStatus.ANNOTATING)
        in_review = sum(
            1 for b in batches
            if b.status in (TaskStatus.SELF_REVIEW, TaskStatus.LEADER_REVIEW, TaskStatus.EXPERT_REVIEW)
        )
        locked = sum(1 for b in batches if b.status == TaskStatus.LOCKED)

        total_batches_all += total
        total_locked_all += locked

        project_progresses.append(ProjectProgress(
            project_id=proj.id,
            project_name=proj.name,
            total_batches=total,
            pending=pending,
            annotating=annotating,
            in_review=in_review,
            locked=locked,
            completion_rate=round(locked / total * 100, 1) if total > 0 else 0.0,
        ))

    users = db.query(User).filter(User.is_active.is_(True)).all()
    user_progresses: List[UserProgress] = []
    for u in users:
        assigned = db.query(TaskBatch).filter(TaskBatch.assigned_to == u.id).count()
        completed = db.query(TaskBatch).filter(
            TaskBatch.assigned_to == u.id, TaskBatch.status == TaskStatus.LOCKED
        ).count()
        user_progresses.append(UserProgress(
            user_id=u.id,
            display_name=u.display_name,
            role=u.role.value,
            assigned_batches=assigned,
            completed_batches=completed,
            completion_rate=round(completed / assigned * 100, 1) if assigned > 0 else 0.0,
        ))

    return ProgressOverview(
        total_projects=len(projects),
        total_batches=total_batches_all,
        total_locked=total_locked_all,
        overall_completion_rate=round(
            total_locked_all / total_batches_all * 100, 1
        ) if total_batches_all > 0 else 0.0,
        projects=project_progresses,
        users=user_progresses,
    )
