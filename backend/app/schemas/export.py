from typing import Optional

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    format: str = Field(default="json", description="json / coco / csv")
    only_locked: bool = True


class ExportOut(BaseModel):
    filename: str
    format: str
    record_count: int
    download_url: Optional[str] = None
