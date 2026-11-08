"""智能体会话入参。"""
from typing import Literal

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field(default="新会话", max_length=120)
    mode: Literal["auto", "rule"] = "auto"


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)