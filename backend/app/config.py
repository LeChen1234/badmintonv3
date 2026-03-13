import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
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

    ALLOW_PUBLIC_REGISTER: bool = True

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
