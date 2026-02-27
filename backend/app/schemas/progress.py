from typing import List, Optional

from pydantic import BaseModel


class ProjectProgress(BaseModel):
    project_id: int
    project_name: str
    total_batches: int
    pending: int
    annotating: int
    in_review: int
    locked: int
    completion_rate: float


class UserProgress(BaseModel):
    user_id: int
    display_name: str
    role: str
    assigned_batches: int
    completed_batches: int
    completion_rate: float


class ProgressOverview(BaseModel):
    total_projects: int
    total_batches: int
    total_locked: int
    overall_completion_rate: float
    projects: List[ProjectProgress]
    users: List[UserProgress]
