"""菜单优化服务：多目标打分 + 约束动作 + 运行留痕。"""
from datetime import timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.optimization import (
    DEFAULT_WEIGHTS,
    assign_actions,
    nutrition_score,
    score_dishes,
)
from app.core.exceptions import BizException
from app.models import Dish, OptimizationRun
from app.services.common import data_max_date, df_records
from app.services.frames import dish_stats_frame


def run_optimization(db: Session, weights: dict | None, protected: list[int],
                     period_days: int) -> dict:
    end = data_max_date(db)
    start = end - timedelta(days=period_days - 1)
    stats = dish_stats_frame(db, start, end)
    nut = pd.read_sql(select(Dish.id.label("dish_id"), Dish.nutrition_json), db.bind)
    nut["nutrition_score"] = nut["nutrition_json"].map(nutrition_score)
    stats = stats.merge(nut[["dish_id", "nutrition_score"]], on="dish_id", how="left")
    stats["nutrition_score"] = stats["nutrition_score"].fillna(0.5)
    acted = assign_actions(score_dishes(stats, weights), protected)
    counts = {k: int(v) for k, v in acted["action"].value_counts().items()}
    cols = ["dish_id", "name", "stall_name", "score",
            "n_margin", "n_satisfaction", "n_nutrition", "n_waste", "action"]
    summary = {"period": {"start": str(start), "end": str(end)}, "counts": counts,
               "protected": protected, "dishes": df_records(acted[cols])}
    run = OptimizationRun(
        scope="all",
        objectives_json={"margin": "毛利率", "satisfaction": "满意度",
                         "nutrition": "营养均衡", "waste": "低浪费"},
        weights_json=weights or DEFAULT_WEIGHTS,
        result_summary=summary,
    )
    db.add(run)
    db.commit()
    return {"run_id": run.id, **summary}


def get_run(db: Session, run_id: int) -> dict:
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise BizException(1002, "优化运行不存在", http_status=404)
    return {"id": run.id, "scope": run.scope, "objectives": run.objectives_json,
            "weights": run.weights_json, "created_at": str(run.created_at),
            **run.result_summary}


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(OptimizationRun).order_by(OptimizationRun.id.desc()).limit(limit)
    ).scalars().all()
    return [{"id": r.id, "scope": r.scope, "weights": r.weights_json,
             "counts": r.result_summary.get("counts", {}), "created_at": str(r.created_at)}
            for r in rows]