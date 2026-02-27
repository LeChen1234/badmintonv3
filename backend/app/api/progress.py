from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.progress import ProgressOverview
from app.core.security import get_current_user
from app.services import progress_service

router = APIRouter(prefix="/progress", tags=["进度监控"])


@router.get("/overview", response_model=ProgressOverview)
def get_progress_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return progress_service.get_overview(db)
