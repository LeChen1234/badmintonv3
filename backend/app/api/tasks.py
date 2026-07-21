from pathlib import Path
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import hashlib
import re

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import require_roles, require_super_admin
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
    save_video_chunk,
    get_uploaded_chunks,
    stage_uploaded_video,
)

router = APIRouter(prefix="/tasks", tags=["任务管理"])
logger = logging.getLogger(__name__)


def _register_video_identity(db: Session, batch: TaskBatch, video_path: Path, filename: str) -> None:
    digest = hashlib.sha256()
    with video_path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    sha256 = digest.hexdigest()
    duplicate = db.query(TaskBatch).filter(TaskBatch.video_sha256 == sha256).first()
    if duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"检测到重复视频；该内容已登记为视频 {duplicate.video_id or duplicate.uuid}",
        )
    batch.video_id = str(uuid4())
    batch.video_sha256 = sha256
    batch.video_filename = filename
    db.commit()


def _enrich_batch(batch: TaskBatch) -> TaskBatchOut:
    players = [
        {
            "id": p.id,
            "uuid": p.uuid,
            "name": p.name,
            "subject_code": p.subject_code,
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
        secondary_assigned_to=batch.secondary_assigned_to,
        secondary_assignee_name=batch.secondary_assignee.display_name if batch.secondary_assignee else None,
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
        match_format=batch.match_format,
        players=players,
        metadata_confirmed=batch.metadata_confirmed,
        metadata_confirmed_at=batch.metadata_confirmed_at,
        selection_metadata=batch.selection_metadata,
        video_id=batch.video_id,
        video_sha256=batch.video_sha256,
        video_filename=batch.video_filename,
        deadline=batch.deadline,
        created_at=batch.created_at,
    )


def _normalize_players(players_input: Optional[List[dict]]) -> List[dict]:
    if not players_input:
        return []

    normalized: List[dict] = []
    for item in players_input[:4]:
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
                "subject_code": ((item.get("subject_code") or "").strip() or None),
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
                subject_code=item.get("subject_code"),
                gender=item.get("gender"),
                age=item.get("age"),
                height_cm=item.get("height_cm"),
            )
            db.add(player)
            db.flush()
        else:
            player.name = item["name"]
            player.subject_code = item.get("subject_code")
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


def _can_access_batch(user: User, batch: TaskBatch) -> bool:
    return user.role != UserRole.STUDENT or user.id in (batch.assigned_to, batch.secondary_assigned_to)


def _queue_video_processing(
    db: Session,
    batch: TaskBatch,
    background_tasks: BackgroundTasks,
    *,
    batch_id: int,
    video_max: int,
    use_yolo_filter: bool,
    motion_percentile: Optional[float],
    source_name: str,
) -> JSONResponse:
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
        source_name=source_name,
    )
    logger.info(
        "[upload] batch=%d queued file=%s max_frames=%d use_yolo=%s motion_percentile=%s",
        batch_id,
        source_name,
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
            "video_id": batch.video_id,
        },
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
    if not _can_access_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务")
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
    update_fields = data.model_dump(exclude_unset=True)
    primary = update_fields.get("assigned_to", batch.assigned_to)
    secondary = update_fields.get("secondary_assigned_to", batch.secondary_assigned_to)
    if primary is not None and primary == secondary:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "主标注员与独立复标员必须是不同用户")
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

    if batch.status == TaskStatus.LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "任务已锁定，元数据不可修改")

    update_data = data.model_dump(exclude_unset=True)
    if "match_date" in update_data:
        batch.match_date = update_data.get("match_date")

    if "match_name" in update_data:
        new_match_name = (update_data.get("match_name") or "").strip() or None
        if new_match_name and new_match_name != batch.match_name and not batch.match_uuid:
            batch.match_uuid = str(uuid4())
        batch.match_name = new_match_name
    if "match_format" in update_data:
        batch.match_format = update_data.get("match_format")

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

    if batch.status == TaskStatus.LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "任务已锁定，元数据不可重新确认")

    if not batch.match_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先填写比赛名称")

    if not batch.match_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先选择比赛日期")

    players = [{"name": p.name} for p in (batch.players or [])]
    expected_players = 2 if batch.match_format == "singles" else 4 if batch.match_format == "doubles" else 0
    if not expected_players:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择比赛类型：单打或双打")
    if len(players) != expected_players:
        label = "单打" if batch.match_format == "singles" else "双打"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label}比赛必须填写 {expected_players} 名运动员")
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
    require_super_admin(current_user)
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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "模型预标注服务未启用")

    require_roles([UserRole.ADMIN, UserRole.EXPERT, UserRole.LEADER])(current_user)
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")

    from app.services.ml_service import trigger_prediction

    return await trigger_prediction(batch.project_id)


@router.get("/{batch_id}/upload/{upload_id}")
def check_uploaded_chunks(
    batch_id: int,
    upload_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询指定任务和文件（通过 upload_id 标识）已经上传了哪些分块，用于断点续传。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_upload_for_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务的上传状态")

    if not re.fullmatch(r"[a-zA-Z0-9_\-=+/]{8,1024}", upload_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "upload_id 无效")

    chunks = get_uploaded_chunks(batch_id, upload_id)
    return {"uploaded_chunks": chunks}


@router.post("/{batch_id}/upload")
async def upload_media(
    batch_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(default=[]),
    file: Optional[UploadFile] = File(None),
    chunk: Optional[UploadFile] = File(None),
    upload_id: Optional[str] = Form(None),
    chunk_index: Optional[int] = Form(None),
    total_chunks: Optional[int] = Form(None),
    original_filename: Optional[str] = Form(None),
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

    if chunk and chunk.filename:
        if batch.media_process_status in (MediaProcessStatus.QUEUED.value, MediaProcessStatus.PROCESSING.value):
            raise HTTPException(status.HTTP_409_CONFLICT, "该任务已有视频正在处理中，请等待当前处理完成")

        if not upload_id or not re.fullmatch(r"[a-zA-Z0-9_\-=+/]{8,1024}", upload_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "upload_id 无效")
        if chunk_index is None or total_chunks is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "缺少 chunk_index 或 total_chunks")
        if total_chunks <= 0 or chunk_index < 0 or chunk_index >= total_chunks:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "分块索引参数不合法")

        source_name = (original_filename or chunk.filename or "video.mp4").strip()
        ext = source_name.lower()
        if not any(ext.endswith(e) for e in ALLOWED_VIDEO_EXT):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持视频分块上传")

        assembled = save_video_chunk(
            batch_id,
            upload_id=upload_id,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_stream=chunk.file,
            original_filename=source_name,
        )
        if not assembled:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "upload_type": "video_chunk",
                    "processing": False,
                    "message": "分块已接收",
                    "upload_id": upload_id,
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                },
            )
        processing_dir = Path(settings.UPLOAD_DIR) / f"batch_{batch_id}" / "_processing"
        staged = next((p for p in processing_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_VIDEO_EXT), None)
        if staged is None:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "视频分块合并失败")
        _register_video_identity(db, batch, staged, source_name)
        return _queue_video_processing(
            db,
            batch,
            background_tasks,
            batch_id=batch_id,
            video_max=video_max,
            use_yolo_filter=use_yolo_filter,
            motion_percentile=motion_percentile,
            source_name=source_name,
        )

    if file and file.filename:
        ext = (file.filename or "").lower()
        if any(ext.endswith(e) for e in ALLOWED_VIDEO_EXT) or "video" in (file.content_type or ""):
            if batch.media_process_status in (MediaProcessStatus.QUEUED.value, MediaProcessStatus.PROCESSING.value):
                raise HTTPException(status.HTTP_409_CONFLICT, "该任务已有视频正在处理中，请等待当前处理完成")

            content = await file.read()
            if len(content) > 500 * 1024 * 1024:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "视频大小不能超过 500MB")

            staged = stage_uploaded_video(batch_id, content, file.filename or "video.mp4")
            _register_video_identity(db, batch, staged, file.filename or "video.mp4")
            return _queue_video_processing(
                db,
                batch,
                background_tasks,
                batch_id=batch_id,
                video_max=video_max,
                use_yolo_filter=use_yolo_filter,
                motion_percentile=motion_percentile,
                source_name=file.filename or "video.mp4",
            )

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持上传单个视频文件，不接受独立图片")


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
    if not _can_access_batch(current_user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权查看该任务")
    frames = db.query(BatchFrame).filter(BatchFrame.task_batch_id == batch_id).order_by(BatchFrame.frame_index).all()
    return [
        {"frame_index": frame.frame_index, "file_path": frame.file_path, "timestamp_ms": frame.timestamp_ms}
        for frame in frames
    ]


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
    if not _can_access_batch(current_user, batch):
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
    box_x: float,
    box_y: float,
    box_w: float,
    box_h: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仅在标注员指定的人物边界框内执行姿态预标注。"""
    batch = task_service.get_task_batch(db, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务批次不存在")
    if not _can_access_batch(current_user, batch):
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
    from app.services.pose_service import PoseBackendUnavailable, predict_persons_detailed_from_image_path
    from app.services.annotation_assist_service import analyze_pose

    try:
        if box_w <= 0 or box_h <= 0 or box_x < 0 or box_y < 0 or box_x + box_w > 100 or box_y + box_h > 100:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "人物边界框超出图像范围")
        persons = predict_persons_detailed_from_image_path(full_path, [box_x, box_y, box_w, box_h])
    except PoseBackendUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    ranked = [
        {**person, "assist": analyze_pose(person["keypoints"])}
        for person in persons
    ]
    return {"persons": ranked, "algorithm_version": "box-constrained-pose-v3"}
