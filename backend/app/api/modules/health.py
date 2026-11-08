"""健康检查（公开）。"""
from fastapi import APIRouter

from app.core.response import ok

router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health")
def health():
    return ok({"status": "ok"})