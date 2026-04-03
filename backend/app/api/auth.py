import base64
import io
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    Token,
    UserLogin,
    UserOut,
    UserRegister,
    ChangePassword,
    ChangePasswordResponse,
    CaptchaOut,
)
from app.core.security import (
    verify_password,
    create_access_token,
    get_current_user,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["认证"])

CAPTCHA_TTL_SECONDS = 300
CAPTCHA_MAX_FAILED_ATTEMPTS = 3
CAPTCHA_LENGTH = 5
CAPTCHA_IMAGE_WIDTH = 180
CAPTCHA_IMAGE_HEIGHT = 64
_captcha_store: dict[str, dict[str, str | datetime | int]] = {}


def _random_captcha_text(length: int = CAPTCHA_LENGTH) -> str:
    charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(charset) for _ in range(length))


def _load_captcha_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for font_path in font_candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_captcha_image(text: str) -> str:
    width, height = CAPTCHA_IMAGE_WIDTH, CAPTCHA_IMAGE_HEIGHT
    image = Image.new("RGB", (width, height), (245, 248, 252))
    draw = ImageDraw.Draw(image)

    for _ in range(8):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        color = (
            random.randint(130, 200),
            random.randint(130, 200),
            random.randint(130, 200),
        )
        draw.line((x1, y1, x2, y2), fill=color, width=1)

    for _ in range(220):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(random.randint(100, 220), random.randint(100, 220), random.randint(100, 220)))

    font = _load_captcha_font(100)
    char_gap = width // (len(text) + 1)
    for i, ch in enumerate(text):
        x = 10 + i * char_gap + random.randint(-2, 2)
        y = 10 + random.randint(-3, 3)
        color = (
            random.randint(20, 90),
            random.randint(20, 90),
            random.randint(20, 90),
        )
        draw.text((x, y), ch, font=font, fill=color)

    image = image.filter(ImageFilter.SMOOTH)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _cleanup_expired_captcha() -> None:
    now = datetime.now(timezone.utc)
    expired_ids = [
        captcha_id
        for captcha_id, item in _captcha_store.items()
        if isinstance(item.get("expires_at"), datetime) and item["expires_at"] <= now
    ]
    for captcha_id in expired_ids:
        _captcha_store.pop(captcha_id, None)


def _verify_captcha(captcha_id: str, captcha_answer: str) -> bool:
    _cleanup_expired_captcha()
    item = _captcha_store.get(captcha_id)
    if not item:
        return False

    if int(item.get("failed_attempts", 0)) >= CAPTCHA_MAX_FAILED_ATTEMPTS:
        _captcha_store.pop(captcha_id, None)
        return False

    answer = str(item.get("answer", "")).strip().lower()
    provided = captcha_answer.strip().lower()
    is_valid = bool(answer and provided and answer == provided)
    if is_valid:
        _captcha_store.pop(captcha_id, None)
        return True

    item["failed_attempts"] = int(item.get("failed_attempts", 0)) + 1
    if int(item["failed_attempts"]) >= CAPTCHA_MAX_FAILED_ATTEMPTS:
        _captcha_store.pop(captcha_id, None)
    return False


@router.get("/captcha", response_model=CaptchaOut)
def get_captcha():
    _cleanup_expired_captcha()
    answer = _random_captcha_text()
    captcha_id = uuid4().hex
    _captcha_store[captcha_id] = {
        "answer": answer,
        "failed_attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=CAPTCHA_TTL_SECONDS),
    }

    return CaptchaOut(
        captcha_id=captcha_id,
        image_base64=_render_captcha_image(answer),
        expires_in_seconds=CAPTCHA_TTL_SECONDS,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserRegister, db: Session = Depends(get_db)):
    if not settings.ALLOW_PUBLIC_REGISTER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "公开注册已关闭，请联系管理员")

    if not _verify_captcha(body.captcha_id, body.captcha_answer):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")

    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=UserRole.STUDENT,
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账户已被禁用")

    token = create_access_token(data={"sub": user.id, "role": user.role.value})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改当前登录用户的密码"""
    # 验证新密码和确认密码是否匹配
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码和确认密码不匹配"
        )
    
    # 验证旧密码是否正确
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="旧密码错误"
        )
    
    # 检查新密码是否与旧密码相同
    if verify_password(body.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与旧密码相同"
        )
    
    # 更新密码
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    
    return ChangePasswordResponse()
