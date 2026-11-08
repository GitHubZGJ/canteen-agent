"""看板接口：核心指标、趋势、排行、时段热力。登录即可读。"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.response import ok
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["看板"],
                   dependencies=[Depends(get_current_user)])


@router.get("/overview")
def overview(start: date | None = None, end: date | None = None,
             db: Session = Depends(get_db)):
    return ok(dashboard_service.overview(db, start, end))


@router.get("/trend")
def trend(start: date | None = None, end: date | None = None,
          db: Session = Depends(get_db)):
    return ok(dashboard_service.trend(db, start, end))


@router.get("/ranking")
def ranking(start: date | None = None, end: date | None = None,
            scope: Literal["stall", "dish"] = "stall",
            limit: int = Query(10, ge=1, le=50),
            db: Session = Depends(get_db)):
    return ok(dashboard_service.ranking(db, start, end, scope, limit))


@router.get("/heatmap")
def heatmap(start: date | None = None, end: date | None = None,
            db: Session = Depends(get_db)):
    return ok(dashboard_service.heatmap(db, start, end))