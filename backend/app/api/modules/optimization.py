"""优化接口：发起菜单优化（经理及以上）、运行列表与详情。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.response import ok
from app.schemas.runs import OptimizationRequest
from app.services import optimization_service

router = APIRouter(prefix="/api/optimization", tags=["优化"],
                   dependencies=[Depends(get_current_user)])


@router.post("/runs")
def create_run(body: OptimizationRequest, db: Session = Depends(get_db),
               _=Depends(require_role("admin", "manager"))):
    return ok(optimization_service.run_optimization(db, body.weights, body.protected, body.period_days))


@router.get("/runs")
def list_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return ok(optimization_service.list_runs(db, limit))


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    return ok(optimization_service.get_run(db, run_id))