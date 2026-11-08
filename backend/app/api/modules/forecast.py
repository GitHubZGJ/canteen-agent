"""预测接口：发起回测运行（经理及以上）、运行列表与详情。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.response import ok
from app.schemas.runs import ForecastRequest
from app.services import forecast_service

router = APIRouter(prefix="/api/forecast", tags=["预测"],
                   dependencies=[Depends(get_current_user)])


@router.post("/runs")
def create_run(body: ForecastRequest, db: Session = Depends(get_db),
               _=Depends(require_role("admin", "manager"))):
    return ok(forecast_service.run_forecast(db, body.dish_id, body.horizon, body.safety_factor))


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return ok(forecast_service.list_runs(db, limit))


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    return ok(forecast_service.get_run(db, run_id))