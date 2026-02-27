import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut
from app.core.security import get_current_user
from app.core.permissions import require_roles
from app.services.label_studio_client import ls_client

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "label-studio", "configs"
)

TEMPLATE_MAP = {
    "skeleton": "skeleton_keypoints.xml",
    "action": "action_classification.xml",
    "combined": "combined_template.xml",
}

router = APIRouter(prefix="/projects", tags=["项目管理"])


def _load_template(template_type: str) -> str:
    filename = TEMPLATE_MAP.get(template_type, TEMPLATE_MAP["combined"])
    path = os.path.join(TEMPLATE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


@router.get("", response_model=List[ProjectOut])
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Project).offset(skip).limit(limit).all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT])(current_user)

    label_config = _load_template(data.template_type)

    ls_project_id = None
    try:
        ls_resp = await ls_client.create_project(
            title=data.name,
            description=data.description or "",
            label_config=label_config,
        )
        ls_project_id = ls_resp.get("id")
    except Exception:
        pass

    project = Project(
        name=data.name,
        description=data.description,
        ls_project_id=ls_project_id,
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    return project


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN, UserRole.EXPERT])(current_user)

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN])(current_user)

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")

    if project.ls_project_id:
        try:
            await ls_client.delete_project(project.ls_project_id)
        except Exception:
            pass

    db.delete(project)
    db.commit()
