from pathlib import Path
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import require_roles
from app.core.security import get_current_user
from app.database import get_db
from app.models.batch_frame import BatchFrame
from app.models.player import Player
from app.models.annotation import FrameAnnotation
from app.models.task_batch import MediaProcessStatus, TaskBatch, TaskStatus
from app.models.user import User, UserRole
from app.schemas.task_batch import TaskBatchCreate, TaskBatchMediaProcessOut, TaskBatchMetadataUpdate, TaskBatchOut, TaskBatchUpdate
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
    players = [
        {
            "id": p.id,
            "uuid": p.uuid,
            "name": p.name,
            "gender": p.gender,
            "age": p.age,
            "height_cm": p.height_cm,
        }
        for p in (batch.players or [])
    ]
    return TaskBatchOut(
        id=batch.id,
        uuid=batch.uuid,
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
        match_uuid=batch.match_uuid,
        match_date=batch.match_date,
        match_name=batch.match_name,
        players=players,
        metadata_confirmed=batch.metadata_confirmed,
        metadata_confirmed_at=batch.metadata_confirmed_at,
        deadline=batch.deadline,
        created_at=batch.created_at,
    )


def _normalize_players(players_input: Optional[List[dict]]) -> List[dict]:
    if not players_input:
        return []

    normalized: List[dict] = []
    for item in players_input[:2]:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "id": item.get("id"),
                "uuid": item.get("uuid") or str(uuid4()),
                "name": name,
                "gender": item.get("gender") if item.get("gender") in ("male", "female") else None,
                "age": item.get("age") if isinstance(item.get("age"), int) and 1 <= item.get("age") <= 99 else None,
                "height_cm": item.get("height_cm") if isinstance(item.get("height_cm"), int) and 80 <= item.get("height_cm") <= 260 else None,
            }
        )
    return normalized


def _sync_batch_players(db: Session, batch: TaskBatch, players_input: Optional[List[dict]]) -> None:
    players = _normalize_players(players_input)
    existing_by_uuid = {p.uuid: p for p in (batch.players or []) if p.uuid}
    keep_ids = set()

    for item in players:
        player = existing_by_uuid.get(item["uuid"])
        if player is None:
            player = Player(
                task_batch_id=batch.id,
                uuid=item["uuid"],
                name=item["name"],
                gender=item.get("gender"),
                age=item.get("age"),
                height_cm=item.get("height_cm"),
            )
            db.add(player)
            db.flush()
        else:
            player.name = item["name"]
            player.gender = item.get("gender")
            player.age = item.get("age")
            player.height_cm = item.get("height_cm")
        keep_ids.add(player.id)

    for player in list(batch.players or []):
        if player.id in keep_ids:
            continue
        ref_count = (
            db.query(FrameAnnotation)
            .filter(FrameAnnotation.selected_player_id == player.id)
            .count()
        )
        if ref_count > 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"选手 {player.name} 已被标注引用，不能删除")
        db.delete(player)


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


@router.put("/{batch_id}/metadata", response_model=TaskBatchOut)
def update_batch_metadata(
    batch_id: int,
    data: TaskBatchMetadataUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_upload_for_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权维护该任务元信息")

    update_data = data.model_dump(exclude_unset=True)
    if "match_date" in update_data:
        batch.match_date = update_data.get("match_date")

    if "match_name" in update_data:
        new_match_name = (update_data.get("match_name") or "").strip() or None
        if new_match_name and new_match_name != batch.match_name and not batch.match_uuid:
            batch.match_uuid = str(uuid4())
        batch.match_name = new_match_name

    if batch.match_name and not batch.match_uuid:
        batch.match_uuid = str(uuid4())

    if "players" in update_data:
        _sync_batch_players(db, batch, update_data.get("players"))

    if update_data:
        batch.metadata_confirmed = False
        batch.metadata_confirmed_at = None

    db.commit()
    db.refresh(batch)
    return _enrich_batch(batch)


@router.post("/{batch_id}/metadata/confirm", response_model=TaskBatchOut)
def confirm_batch_metadata(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_upload_for_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权确认该任务元信息")

    if not batch.match_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先填写比赛名称")

    if not batch.match_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先选择比赛日期")

    players = [{"name": p.name} for p in (batch.players or [])]
    if not players:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请至少填写一位选手名称")
    if any(not (p.get("name") or "").strip() for p in players):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "选手名称为必填项")

    if batch.match_name and not batch.match_uuid:
        batch.match_uuid = str(uuid4())

    batch.metadata_confirmed = True
    batch.metadata_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(batch)
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
