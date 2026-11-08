"""建议工单入参。"""
from typing import Literal

from pydantic import BaseModel, Field


class SuggestionCreate(BaseModel):
    type: Literal["menu_change", "forecast_adjust", "promotion", "other"] = "other"
    title: str = Field(min_length=2, max_length=120)
    content: dict = Field(default_factory=dict)
    run_id: int | None = None


class ReviewIn(BaseModel):
    approve: bool
    note: str = Field(default="", max_length=500)


class NoteIn(BaseModel):
    note: str = Field(default="", max_length=500)