from typing import Optional

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    format: str = Field(default="coco", description="coco / csv / vlm")
    only_locked: bool = True


class ExportOut(BaseModel):
    filename: str
    format: str
    record_count: int
    download_url: Optional[str] = None
