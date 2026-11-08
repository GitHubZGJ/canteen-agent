"""菜品分析接口：组合、浪费、评价、营养。登录即可读。"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.response import ok
from app.services import analysis_service

router = APIRouter(prefix="/api/analysis", tags=["分析"],
                   dependencies=[Depends(get_current_user)])


@router.get("/portfolio")
def portfolio(start: date | None = None, end: date | None = None,
              db: Session = Depends(get_db)):
    return ok(analysis_service.portfolio(db, start, end))


@router.get("/waste")
def waste(start: date | None = None, end: date | None = None,
          db: Session = Depends(get_db)):
    return ok(analysis_service.waste(db, start, end))


@router.get("/reviews")
def reviews(start: date | None = None, end: date | None = None,
            db: Session = Depends(get_db)):
    return ok(analysis_service.reviews(db, start, end))


@router.get("/nutrition")
def nutrition(start: date | None = None, end: date | None = None,
              db: Session = Depends(get_db)):
    return ok(analysis_service.nutrition(db, start, end))