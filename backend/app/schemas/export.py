from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    format: str = Field(default="json", description="json / coco / csv")
    only_locked: bool = True


class ExportOut(BaseModel):
    filename: str
    format: str
    record_count: int
    download_url: Optional[str] = None
    dataset_id: Optional[str] = None
    dataset_sha256: Optional[str] = None
    split_record_counts: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    release_ready: bool = False
    quality_gates: Dict[str, bool] = Field(default_factory=dict)
