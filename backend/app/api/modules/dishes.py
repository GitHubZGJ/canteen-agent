"""菜品接口：分页列表与单品分析。登录即可读。"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.response import ok
from app.models import Dish, Stall
from app.services import dish_service

router = APIRouter(prefix="/api/dishes", tags=["菜品"],
                   dependencies=[Depends(get_current_user)])


@router.get("/options")
def dish_options(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Dish.id, Dish.name, Stall.name.label("stall_name"))
        .join(Stall, Dish.stall_id == Stall.id).order_by(Dish.id)
    ).all()
    return ok([{"id": r.id, "name": r.name, "stall_name": r.stall_name} for r in rows])


@router.get("")
def list_dishes(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                stall_id: int | None = None, category: str | None = None,
                keyword: str | None = None,
                start: date | None = None, end: date | None = None,
                db: Session = Depends(get_db)):
    return ok(dish_service.list_dishes(db, page, page_size, stall_id, category,
                                       keyword, start, end))


@router.get("/{dish_id}/analysis")
def dish_analysis(dish_id: int, start: date | None = None, end: date | None = None,
                  db: Session = Depends(get_db)):
    return ok(dish_service.dish_analysis(db, dish_id, start, end))