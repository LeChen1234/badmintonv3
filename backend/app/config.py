import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import List

def _resolve_project_root() -> Path:
    """Locate the repository/runtime root in both source and Docker layouts."""
    config_file = Path(__file__).resolve()
    source_root = config_file.parents[2]
    runtime_root = config_file.parents[1]
    if (source_root / "config").is_dir():
        return source_root
    if (runtime_root / "config").is_dir():
        return runtime_root
    return source_root


PROJECT_ROOT = _resolve_project_root()


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production",
        validation_alias=AliasChoices("BACKEND_SECRET_KEY", "SECRET_KEY"),
    )
    ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("BACKEND_ALGORITHM", "ALGORITHM"),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=480,
        validation_alias=AliasChoices("BACKEND_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES"),
    )
    CORS_ORIGINS: str = Field(
        default='["*"]',
        validation_alias=AliasChoices("BACKEND_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    SQLITE_DB_PATH: str = str(PROJECT_ROOT / "data" / "badminton.db")

    ENABLE_ML_BACKEND: bool = False
    ML_BACKEND_HOST: str = "http://localhost:9090"
    LABEL_STUDIO_HOST: str = "http://localhost:8080"
    LABEL_STUDIO_API_KEY: str = ""

    DATA_DIR: str = str(PROJECT_ROOT / "data")
    EXPORT_DIR: str = str(PROJECT_ROOT / "data" / "exports")
    UPLOAD_DIR: str = str(PROJECT_ROOT / "data" / "uploads")
    BACKUP_DIR: str = str(PROJECT_ROOT / "data" / "backups")
    ENABLE_AUTO_BACKUP: bool = True
    BACKUP_INTERVAL_MINUTES: int = 60
    BACKUP_KEEP_COUNT: int = 24

    ALLOW_PUBLIC_REGISTER: bool = True
    ANNOTATION_TAXONOMY_PATH: str = str(PROJECT_ROOT / "config" / "annotation_taxonomy.json")
    RESEARCH_PROTOCOL_PATH: str = str(PROJECT_ROOT / "config" / "research_protocol.json")
    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = ""

    # Hybrid multi-person pose assistance. All values can be overridden by .env.
    POSE_YOLO_MODEL: str = "yolov8m-pose.pt"
    POSE_YOLO_CONFIDENCE: float = 0.12
    POSE_YOLO_IOU: float = 0.55
    POSE_YOLO_IMAGE_SIZE: int = 960
    POSE_MAX_PERSONS: int = 20
    POSE_ENABLE_TILING: bool = True
    POSE_TILE_MIN_SIDE: int = 1080
    POSE_MIN_VISIBLE_JOINTS: int = 5
    POSE_DEDUP_CONTAINMENT: float = 0.72
    POSE_DEDUP_KEYPOINT_DISTANCE: float = 0.10
    POSE_BOX_MAX_PERSONS: int = 1
    POSE_BOX_PADDING_RATIO: float = 0.15

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY == "dev-secret-key-change-in-production" or len(self.SECRET_KEY) < 32:
                raise ValueError("Production requires BACKEND_SECRET_KEY with at least 32 characters")
            if "*" in self.cors_origin_list:
                raise ValueError("Production CORS origins must be explicit")
        return self

    @property
    def database_url(self) -> str:
        db_dir = os.path.dirname(self.SQLITE_DB_PATH)
        os.makedirs(db_dir, exist_ok=True)
        return f"sqlite:///{self.SQLITE_DB_PATH}"

    @property
    def cors_origin_list(self) -> List[str]:
        import json
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["*"]

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
    )


settings = Settings()
