from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.core.permissions import require_roles
from app.services.ml_service import trigger_prediction

router = APIRouter(prefix="/annotations", tags=["标注管理"])


@router.post("/{project_id}/trigger-ml")
async def trigger_ml_annotation(
    project_id: int,
    current_user: User = Depends(get_current_user),
):
    """Trigger ML backend to generate initial annotations for a project."""
    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    result = await trigger_prediction(project_id)
    return result
