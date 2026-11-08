"""报告接口：生成周报、列表与详情。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.response import ok
from app.services import report_service

router = APIRouter(prefix="/api/reports", tags=["报告"],
                   dependencies=[Depends(get_current_user)])


class WeeklyIn(BaseModel):
    end: date | None = None
    days: int = Field(7, ge=1, le=30)


@router.post("/weekly")
def generate_weekly(body: WeeklyIn, db: Session = Depends(get_db),
                    _=Depends(require_role("admin", "manager"))):
    return ok(report_service.generate_weekly(db, body.end, body.days))


@router.get("")
def list_reports(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return ok(report_service.list_reports(db, limit))


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    return ok(report_service.get_report(db, report_id))