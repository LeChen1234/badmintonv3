from typing import Any, Dict

from pydantic import BaseModel, Field


class ActiveRoundCreate(BaseModel):
    dataset_id: str = Field(min_length=8, max_length=64)
    model_version: str = Field(min_length=1, max_length=128)
    selection_strategy: str = Field(default="information_functional", max_length=64)
    annotation_count: int = Field(gt=0)
    annotation_hours: float = Field(gt=0, le=100000)
    macro_f1_mean: float = Field(ge=0, le=1)
    macro_f1_std: float = Field(default=0, ge=0, le=1)
    repeat_count: int = Field(default=5, ge=2, le=100)
    balanced_accuracy_mean: float = Field(ge=0, le=1)
    nll_mean: float = Field(ge=0)
    ece_mean: float = Field(ge=0, le=1)
    component_gains: Dict[str, float] = Field(default_factory=dict)
    statistical_comparison: Dict[str, Any] = Field(default_factory=dict)
