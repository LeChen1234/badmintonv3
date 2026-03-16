from pathlib import Path
from typing import List, Optional

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import require_roles
from app.core.security import get_current_user
from app.database import get_db
from app.models.batch_frame import BatchFrame
from app.models.task_batch import MediaProcessStatus, TaskBatch, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task_batch import TaskBatchCreate, TaskBatchMediaProcessOut, TaskBatchOut, TaskBatchUpdate
from app.services import task_service
from app.services.upload_service import (
    ALLOWED_IMAGE_EXT,
    ALLOWED_VIDEO_EXT,
    _save_uploaded_images,
    cleanup_processing_dir,
    process_uploaded_video_in_background,
    replace_frames_for_batch,
    stage_uploaded_video,
)

router = APIRouter(prefix="/tasks", tags=["任务管理"])
logger = logging.getLogger(__name__)


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
        media_process_status=batch.media_process_status,
        media_process_message=batch.media_process_message,
        media_process_started_at=batch.media_process_started_at,
        media_process_finished_at=batch.media_process_finished_at,
        deadline=batch.deadline,
        created_at=batch.created_at,
    )


def _can_upload_for_batch(user: User, batch: TaskBatch) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER):
        return True
    return batch.assigned_to == user.id


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
        db,
        project_id=project_id,
        assigned_to=assigned_to,
        status=task_status,
        skip=skip,
        limit=limit,
    )
    return [_enrich_batch(batch) for batch in batches]


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


@router.get("/{batch_id}/media-process-status", response_model=TaskBatchMediaProcessOut)
def get_media_process_status(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_upload_for_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务上传状态")
    return TaskBatchMediaProcessOut(
        task_batch_id=batch.id,
        media_process_status=batch.media_process_status,
        media_process_message=batch.media_process_message,
        media_process_started_at=batch.media_process_started_at,
        media_process_finished_at=batch.media_process_finished_at,
        total_frames=batch.total_frames,
    )


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


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_roles([UserRole.ADMIN])(current_user)
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    task_service.delete_task_batch(db, batch)
    return None


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

    return await trigger_prediction(batch.project_id)


@router.post("/{batch_id}/upload")
async def upload_media(
    batch_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(None),
    max_frames: Optional[int] = Form(None),
    use_yolo_filter: bool = Form(False),
    motion_percentile: Optional[float] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传多张图片或一个视频。图片同步导入；视频转为后台任务处理。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_upload_for_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为该任务上传媒体")

    video_max = max(1, min(2000, max_frames or 500))
    if motion_percentile is not None and not (0 <= motion_percentile <= 100):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "动作百分位必须在 0-100 之间")

    if file and file.filename:
        ext = (file.filename or "").lower()
        if any(ext.endswith(e) for e in ALLOWED_VIDEO_EXT) or "video" in (file.content_type or ""):
            if batch.media_process_status in (MediaProcessStatus.QUEUED.value, MediaProcessStatus.PROCESSING.value):
                raise HTTPException(status.HTTP_409_CONFLICT, "该任务已有视频正在处理中，请等待当前处理完成")

            content = await file.read()
            if len(content) > 500 * 1024 * 1024:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "视频大小不能超过 500MB")

            stage_uploaded_video(batch_id, content, file.filename or "video.mp4")
            task_service.update_media_process_state(
                db,
                batch,
                MediaProcessStatus.QUEUED,
                message="视频已上传，等待后台处理。",
                started_at=None,
                finished_at=None,
            )
            background_tasks.add_task(
                process_uploaded_video_in_background,
                batch_id,
                max_frames=video_max,
                use_yolo=use_yolo_filter,
                motion_percentile=motion_percentile,
                source_name=file.filename or "video.mp4",
            )
            logger.info(
                "[upload] batch=%d queued file=%s max_frames=%d use_yolo=%s motion_percentile=%s",
                batch_id,
                file.filename,
                video_max,
                use_yolo_filter,
                motion_percentile,
            )
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "upload_type": "video",
                    "processing": True,
                    "media_process_status": MediaProcessStatus.QUEUED.value,
                    "message": "视频已上传，正在后台处理中。",
                },
            )

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请上传至少一张图片或一个视频文件")

    image_files = []
    for upload in files:
        if not upload.filename:
            continue
        ext = (upload.filename or "").lower()
        if not any(ext.endswith(e) for e in ALLOWED_IMAGE_EXT):
            continue
        content = await upload.read()
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"单张图片不能超过 20MB: {upload.filename}")
        image_files.append((content, upload.filename))

    if not image_files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "未包含支持的图片格式 (jpg/png/bmp/gif/webp)")

    cleanup_processing_dir(batch_id)
    entries = _save_uploaded_images(batch_id, image_files)
    replace_frames_for_batch(db, batch, entries)
    task_service.update_media_process_state(
        db,
        batch,
        MediaProcessStatus.COMPLETED,
        message=f"图片上传完成，已导入 {len(entries)} 张图片。",
        started_at=None,
        finished_at=None,
    )
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
    return [{"frame_index": frame.frame_index, "file_path": frame.file_path} for frame in frames]


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
    batch_frame = db.query(BatchFrame).filter(
        BatchFrame.task_batch_id == batch_id,
        BatchFrame.frame_index == frame_index,
    ).first()
    if not batch_frame:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该帧不存在")
    full_path = Path(settings.UPLOAD_DIR) / batch_frame.file_path
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
    batch_frame = db.query(BatchFrame).filter(
        BatchFrame.task_batch_id == batch_id,
        BatchFrame.frame_index == frame_index,
    ).first()
    if not batch_frame:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该帧不存在")
    full_path = Path(settings.UPLOAD_DIR) / batch_frame.file_path
    if not full_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "帧文件不存在")
    from app.services.pose_service import predict_keypoints_multi_from_image_path

    persons = predict_keypoints_multi_from_image_path(full_path)
    return {"persons": [{"keypoints": person} for person in persons]}
