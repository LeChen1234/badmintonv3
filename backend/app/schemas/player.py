from pydantic import BaseModel, Field
from typing import Optional


class PlayerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class PlayerOut(BaseModel):
    id: int
    uuid: str
    task_batch_id: int
    name: str

    model_config = {"from_attributes": True}
