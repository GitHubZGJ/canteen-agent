"""统一响应 Result<T>：{code, msg, data}，0 表示成功。"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    code: int = 0
    msg: str = "ok"
    data: T | None = None


def ok(data: Any = None, msg: str = "ok") -> dict:
    return {"code": 0, "msg": msg, "data": data}