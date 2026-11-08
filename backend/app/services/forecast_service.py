"""备餐量预测服务：全历史回测、运行留痕、备餐节约测算。"""
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.analytics.forecast import (
    error_metrics,
    holt_winters,
    is_sufficient,
    prediction_band,
    seasonal_naive,
)
from app.core.exceptions import ERR_PARAM, BizException
from app.models import Dish, ForecastResult, ForecastRun, Order, WasteRecord
from app.services.common import slot_of_hour
from app.services.frames import items_frame

SLOTS = ("breakfast", "lunch", "dinner")


def _history_range(db: Session) -> tuple[date, date]:
    lo, hi = db.execute(
        select(func.min(func.date(Order.dining_time)), func.max(func.date(Order.dining_time)))
    ).one()
    if lo is None:
        raise BizException(ERR_PARAM, "暂无经营数据，请先生成或导入数据")
    return date.fromisoformat(str(lo)), date.fromisoformat(str(hi))


def _aggregate(actuals: list, preds: list) -> dict:
    if not actuals:
        return {"mae": None, "mape": None}
    return error_metrics(np.concatenate(actuals), np.concatenate(preds))


def run_forecast(db: Session, dish_id: int | None, horizon: int, safety_factor: float) -> dict:
    start, end = _history_range(db)
    if (end - start).days + 1 < horizon + 28:
        raise BizException(ERR_PARAM, "数据跨度不足以回测（至少 horizon+28 天）")
    if dish_id is not None and db.get(Dish, dish_id) is None:
        raise BizException(1002, "菜品不存在", http_status=404)

    items = items_frame(db, start, end)
    items["slot"] = items["dining_time"].dt.hour.map(slot_of_hour)
    items["d"] = items["dining_time"].dt.date
    all_dates = pd.date_range(start, end)
    train_end = end - timedelta(days=horizon)
    test_dates = pd.date_range(train_end + timedelta(days=1), end)
    train_ts = pd.Timestamp(train_end)
    n_days = (end - start).days + 1

    dish_ids = [dish_id] if dish_id is not None else sorted(items["dish_id"].unique().tolist())
    dish_stall = dict(db.execute(select(Dish.id, Dish.stall_id)).all())
    stall_dish_count = pd.Series(dish_stall).value_counts().to_dict()
    stall_slot_daily = (
        items[items["slot"].isin(SLOTS)]
        .assign(sid=lambda x: x["dish_id"].map(dish_stall))
        .groupby(["sid", "slot"])["quantity"].sum() / n_days
    )

    run = ForecastRun(dish_id=dish_id, target_start=test_dates[0].date(), target_end=end,
                      model="holt_winters")
    db.add(run)
    db.flush()

    result_rows, details = [], []
    chosen_a, chosen_p, naive_a, naive_p, hw_a, hw_p = [], [], [], [], [], []
    naive_sub_a, naive_sub_p = [], []  # 与 HW 同子集的基线，用于公平对比
    fallback_count = 0
    daily_forecast = dict.fromkeys(dish_ids, 0.0)

    for did in dish_ids:
        sid = dish_stall[did]
        for slot in SLOTS:
            sub = items[(items["dish_id"] == did) & (items["slot"] == slot)]
            series = (sub.groupby("d")["quantity"].sum()
                      .reindex(all_dates.date, fill_value=0).astype(float))
            series.index = all_dates
            train = series.loc[:train_ts]
            actual = series.loc[test_dates].to_numpy()
            naive = seasonal_naive(series, list(test_dates))
            if is_sufficient(train):
                try:
                    pred = holt_winters(train, horizon)
                    model = "holt_winters"
                except (ValueError, ArithmeticError, np.linalg.LinAlgError):
                    # 拟合失败（如数值不稳定）回退到同口径基线，并计数留痕
                    pred = naive.copy()
                    model = "seasonal_naive"
                    fallback_count += 1
            else:
                mean = float(stall_slot_daily.get((sid, slot), 0.0)) / stall_dish_count.get(sid, 1)
                pred = np.full(horizon, mean)
                model = "stall_mean"
                fallback_count += 1
            lower, upper = prediction_band(pred, float(np.std(actual - pred)))
            cm, nm = error_metrics(actual, pred), error_metrics(actual, naive)
            chosen_a.append(actual)
            chosen_p.append(pred)
            naive_a.append(actual)
            naive_p.append(naive)
            if model == "holt_winters":
                hw_a.append(actual)
                hw_p.append(pred)
                naive_sub_a.append(actual)
                naive_sub_p.append(naive)
            daily_forecast[did] += float(pred.mean())
            for i, d in enumerate(test_dates):
                result_rows.append({
                    "run_id": run.id, "dish_id": did, "date": d.date(), "slot": slot,
                    "predicted_qty": round(float(pred[i]), 1),
                    "lower": round(float(lower[i]), 1), "upper": round(float(upper[i]), 1),
                })
            details.append({"dish_id": did, "slot": slot, "model": model,
                            "mae": cm["mae"], "mape": cm["mape"],
                            "naive_mae": nm["mae"], "naive_mape": nm["mape"]})

    chosen_m, naive_m, hw_m = _aggregate(chosen_a, chosen_p), _aggregate(naive_a, naive_p), _aggregate(hw_a, hw_p)
    naive_sub_m = _aggregate(naive_sub_a, naive_sub_p)

    # 备餐节约测算：按预测 × 安全系数备餐，对比历史平均浪费
    waste_hist = dict(db.execute(
        select(WasteRecord.dish_id, func.avg(WasteRecord.wasted_qty)).group_by(WasteRecord.dish_id)
    ).all())
    total_saving, prep_rows = 0.0, []
    for did in dish_ids:
        demand = daily_forecast[did]
        suggested = float(np.ceil(demand * safety_factor))
        hist_wasted = float(waste_hist.get(did, 0.0))
        saving = max(0.0, hist_wasted - max(0.0, suggested - demand))
        total_saving += saving
        prep_rows.append({"dish_id": did, "avg_daily_forecast": round(demand, 1),
                          "suggested_prep": int(suggested), "hist_avg_wasted": round(hist_wasted, 1),
                          "estimated_saving": round(saving, 1)})

    run.mae, run.mape = chosen_m["mae"], chosen_m["mape"]
    run.params_json = {
        "horizon": horizon, "safety_factor": safety_factor,
        "dish_count": len(dish_ids), "fallback_count": fallback_count,
        "chosen": chosen_m, "seasonal_naive": naive_m, "holt_winters": hw_m,
        "seasonal_naive_same_subset": naive_sub_m,
        "holt_winters_pairs": len(hw_a),
        "total_estimated_saving": round(total_saving, 1),
        "prep_suggestions": prep_rows,
    }
    db.execute(insert(ForecastResult), result_rows)
    db.commit()
    return {"run_id": run.id,
            "metrics": {"chosen": chosen_m, "seasonal_naive": naive_m,
                        "holt_winters": hw_m, "seasonal_naive_same_subset": naive_sub_m,
                        "holt_winters_pairs": len(hw_a)},
            "fallback_count": fallback_count, "total_estimated_saving": round(total_saving, 1),
            "prep_suggestions": prep_rows, "details": details}


def get_run(db: Session, run_id: int) -> dict:
    run = db.get(ForecastRun, run_id)
    if run is None:
        raise BizException(1002, "预测运行不存在", http_status=404)
    names = dict(db.execute(select(Dish.id, Dish.name)).all())
    items = items_frame(db, run.target_start, run.target_end)
    items["slot"] = items["dining_time"].dt.hour.map(slot_of_hour)
    items["d"] = items["dining_time"].dt.date
    actual_map = (items.groupby(["dish_id", "slot", "d"])["quantity"].sum().to_dict())
    rows = db.execute(
        select(ForecastResult).where(ForecastResult.run_id == run_id)
        .order_by(ForecastResult.dish_id, ForecastResult.slot, ForecastResult.date)
    ).scalars().all()
    groups: dict[tuple, dict] = {}
    for r in rows:
        key = (r.dish_id, r.slot)
        g = groups.setdefault(key, {"dish_id": r.dish_id, "dish_name": names.get(r.dish_id, ""),
                                    "slot": r.slot, "points": []})
        g["points"].append({"date": str(r.date), "predicted": r.predicted_qty,
                            "lower": r.lower, "upper": r.upper,
                            "actual": int(actual_map.get((r.dish_id, r.slot, r.date), 0))})
    return {"id": run.id, "dish_id": run.dish_id, "model": run.model,
            "mae": run.mae, "mape": run.mape, "params": run.params_json,
            "target_start": str(run.target_start), "target_end": str(run.target_end),
            "created_at": str(run.created_at), "series": list(groups.values())}


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    rows = db.execute(
        select(ForecastRun).order_by(ForecastRun.id.desc()).limit(limit)
    ).scalars().all()
    return [{"id": r.id, "dish_id": r.dish_id, "model": r.model, "mae": r.mae, "mape": r.mape,
             "target_start": str(r.target_start), "target_end": str(r.target_end),
             "created_at": str(r.created_at)} for r in rows]