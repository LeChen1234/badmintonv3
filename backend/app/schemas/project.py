from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    template_type: str = Field(default="combined", description="skeleton / action / combined")


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    uuid: str
    name: str
    description: Optional[str] = None
    ls_project_id: Optional[int] = None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
