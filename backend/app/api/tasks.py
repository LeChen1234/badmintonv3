from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.models.task_batch import TaskBatch, TaskStatus
from app.models.batch_frame import BatchFrame
from app.schemas.task_batch import TaskBatchCreate, TaskBatchUpdate, TaskBatchOut
from app.core.security import get_current_user
from app.core.permissions import require_roles
from app.services import task_service
from app.services.upload_service import (
    ALLOWED_IMAGE_EXT,
    ALLOWED_VIDEO_EXT,
    add_frames_to_batch,
    replace_frames_for_batch,
    save_uploaded_video,
    _save_uploaded_images,
)

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
    from app.config import settings as app_settings
    if not app_settings.ENABLE_ML_BACKEND:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "大模型标注功能未启用")

    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    from app.services.ml_service import trigger_prediction
    result = await trigger_prediction(batch.project_id)
    return result


def _can_upload_for_batch(user: User, batch: TaskBatch) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER):
        return True
    return batch.assigned_to == user.id


@router.post("/{batch_id}/upload")
async def upload_media(
    batch_id: int,
    files: List[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(None),
    max_frames: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传多张图片或一个视频。图片时传 files；视频时传 file；视频可传 max_frames 控制抽帧上限（默认 500）。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_upload_for_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为该任务上传媒体")

    video_max = max(1, min(2000, max_frames or 500))

    # 视频：单文件
    if file and file.filename:
        ext = (file.filename or "").lower()
        if any(ext.endswith(e) for e in ALLOWED_VIDEO_EXT) or "video" in (file.content_type or ""):
            content = await file.read()
            if len(content) > 500 * 1024 * 1024:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "视频大小不能超过 500MB")
            entries = save_uploaded_video(batch_id, content, file.filename or "video.mp4", max_frames=video_max)
            replace_frames_for_batch(db, batch, entries)
            return {"upload_type": "video", "frame_count": len(entries), "message": f"已提取 {len(entries)} 帧"}

    # 图片：多文件
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传至少一张图片或一个视频文件")

    image_files = []
    for f in files:
        if not f.filename:
            continue
        ext = (f.filename or "").lower()
        if not any(ext.endswith(e) for e in ALLOWED_IMAGE_EXT):
            continue
        content = await f.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"单张图片不能超过 20MB: {f.filename}")
        image_files.append((content, f.filename))

    if not image_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "未包含支持的图片格式 (jpg/png/bmp/gif/webp)")

    entries = _save_uploaded_images(batch_id, image_files)
    replace_frames_for_batch(db, batch, entries)
    return {"upload_type": "images", "frame_count": len(entries), "message": f"已上传 {len(entries)} 张图片"}


@router.get("/{batch_id}/frames")
def list_frames(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出该任务批次下所有帧的 frame_index 与 file_path。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if current_user.role == UserRole.STUDENT and batch.assigned_to != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务")
    frames = db.query(BatchFrame).filter(BatchFrame.task_batch_id == batch_id).order_by(BatchFrame.frame_index).all()
    return [{"frame_index": f.frame_index, "file_path": f.file_path} for f in frames]


@router.get("/{batch_id}/frame/{frame_index}/image")
def get_frame_image(
    batch_id: int,
    frame_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回该帧的图片文件。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if current_user.role == UserRole.STUDENT and batch.assigned_to != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务")
    bf = db.query(BatchFrame).filter(
        BatchFrame.task_batch_id == batch_id,
        BatchFrame.frame_index == frame_index,
    ).first()
    if not bf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该帧不存在")
    full_path = Path(settings.UPLOAD_DIR) / bf.file_path
    if not full_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "帧文件不存在")
    return FileResponse(str(full_path), media_type="image/jpeg")


@router.get("/{batch_id}/frame/{frame_index}/predict-keypoints")
def predict_keypoints(
    batch_id: int,
    frame_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """算法辅助：对当前帧做姿态估计，返回 25 关键点（人体部分由 MediaPipe 预测，球拍两点为 0）。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if current_user.role == UserRole.STUDENT and batch.assigned_to != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务")
    bf = db.query(BatchFrame).filter(
        BatchFrame.task_batch_id == batch_id,
        BatchFrame.frame_index == frame_index,
    ).first()
    if not bf:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该帧不存在")
    full_path = Path(settings.UPLOAD_DIR) / bf.file_path
    if not full_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "帧文件不存在")
    from app.services.pose_service import predict_keypoints_multi_from_image_path
    persons = predict_keypoints_multi_from_image_path(full_path)
    return {"persons": [{"keypoints": p} for p in persons]}
