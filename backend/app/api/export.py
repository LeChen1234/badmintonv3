import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.export import ExportRequest, ExportOut
from app.core.security import get_current_user
from app.services.label_studio_client import ls_client
from app.services import export_service

router = APIRouter(prefix="/export", tags=["数据导出"])


@router.post("/{project_id}", response_model=ExportOut)
async def export_project(
    project_id: int,
    req: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if not project.ls_project_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "项目未关联 Label Studio")

    try:
        annotations = await ls_client.export_project(project.ls_project_id, "JSON")
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"导出失败: {e}")

    if not isinstance(annotations, list):
        annotations = []

    fmt = req.format.lower()
    if fmt == "coco":
        data = export_service.convert_to_coco(annotations)
        filename = f"project_{project_id}_coco.json"
    elif fmt == "csv":
        data = export_service.convert_to_csv(annotations)
        filename = f"project_{project_id}.csv"
    elif fmt == "vlm":
        data = export_service.convert_to_vlm(annotations)
        filename = f"project_{project_id}_vlm.json"
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的格式: {fmt}")

    return ExportOut(
        filename=filename,
        format=fmt,
        record_count=len(annotations),
    )


@router.post("/{project_id}/download")
async def download_export(
    project_id: int,
    req: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    if not project.ls_project_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "项目未关联 Label Studio")

    try:
        annotations = await ls_client.export_project(project.ls_project_id, "JSON")
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"导出失败: {e}")

    if not isinstance(annotations, list):
        annotations = []

    fmt = req.format.lower()
    if fmt == "coco":
        content = json.dumps(export_service.convert_to_coco(annotations), ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"project_{project_id}_coco.json"
    elif fmt == "csv":
        content = export_service.convert_to_csv(annotations)
        media_type = "text/csv"
        filename = f"project_{project_id}.csv"
    elif fmt == "vlm":
        content = json.dumps(export_service.convert_to_vlm(annotations), ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"project_{project_id}_vlm.json"
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的格式: {fmt}")

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
