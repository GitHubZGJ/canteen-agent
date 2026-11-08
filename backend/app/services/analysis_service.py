"""菜品分析服务：组合四象限、滞销、浪费、评价、营养。"""
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.portfolio import (
    SLOW_DAYS,
    SLOW_RATIO,
    add_abc,
    add_quadrant,
    find_slow_movers,
)
from app.analytics.reviews import summarize_reviews, weighted_nutrition
from app.analytics.waste import find_waste_alerts
from app.models import Dish
from app.services.common import df_records, resolve_range
from app.services.frames import (
    dish_base,
    dish_stats_frame,
    items_frame,
    reviews_frame,
    waste_frame,
)


def _slow_movers(db: Session, dish_df: pd.DataFrame, start: date, end: date) -> list[dict]:
    df = items_frame(db, start, end)
    all_dates = list(pd.date_range(start, end).date)
    if len(df):
        df["d"] = df["dining_time"].dt.date
        pivot = df.pivot_table(index="dish_id", columns="d", values="quantity",
                               aggfunc="sum", fill_value=0)
    else:
        pivot = pd.DataFrame(columns=all_dates, dtype=float)
    pivot = pivot.reindex(index=dish_df["dish_id"], columns=all_dates, fill_value=0)
    info = dish_df.set_index("dish_id")
    slow = []
    for _, group in dish_df.groupby("stall_id"):
        sub = pivot.loc[group["dish_id"]]
        stall_avg = sub.sum(axis=0) / len(group)  # 档口当日菜品均值销量
        for dish_id in find_slow_movers(sub, stall_avg):
            slow.append({
                "dish_id": int(dish_id),
                "name": info.loc[dish_id, "name"],
                "stall_name": info.loc[dish_id, "stall_name"],
                "avg_daily_qty": round(float(sub.loc[dish_id].tail(SLOW_DAYS).mean()), 1),
                "threshold_qty": round(SLOW_RATIO * float(stall_avg.tail(SLOW_DAYS).mean()), 1),
            })
    return slow


def portfolio(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    df = dish_stats_frame(db, start, end)
    df, thresholds = add_quadrant(df)
    df = add_abc(df)
    return {"range": {"start": str(start), "end": str(end)},
            "thresholds": thresholds, "dishes": df_records(df),
            "slow_movers": _slow_movers(db, df, start, end)}


def waste(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    raw = waste_frame(db, start, end)
    base = dish_base(db)[["dish_id", "name", "stall_name"]]
    by_dish = (raw.groupby("dish_id")[["prepared_qty", "wasted_qty"]].sum()
               .rename(columns={"prepared_qty": "prepared", "wasted_qty": "wasted"})
               .reset_index().merge(base, on="dish_id", how="right")
               .fillna({"prepared": 0, "wasted": 0}))
    prepared, wasted = int(by_dish["prepared"].sum()), int(by_dish["wasted"].sum())
    alerts = find_waste_alerts(by_dish).sort_values("wasted", ascending=False)
    top = by_dish.sort_values("wasted", ascending=False).head(10).copy()
    top["waste_rate"] = (top["wasted"]
                         / top["prepared"].where(top["prepared"] > 0)).fillna(0.0).round(4)
    by_reason = (raw.groupby("waste_reason")["wasted_qty"].sum()
                 .sort_values(ascending=False))
    daily = raw.groupby("date")[["prepared_qty", "wasted_qty"]].sum().reindex(
        pd.date_range(start, end).date, fill_value=0)
    return {
        "range": {"start": str(start), "end": str(end)},
        "totals": {"prepared": prepared, "wasted": wasted,
                   "rate": round(wasted / prepared, 4) if prepared else 0.0},
        "top_dishes": df_records(top),
        "alerts": df_records(alerts),
        "by_reason": [{"reason": k, "wasted": int(v)} for k, v in by_reason.items()],
        "trend": [{"date": str(d), "prepared": int(r["prepared_qty"]),
                   "wasted": int(r["wasted_qty"]),
                   "rate": round(float(r["wasted_qty"]) / float(r["prepared_qty"]), 4)
                   if r["prepared_qty"] else 0.0} for d, r in daily.iterrows()],
    }


def reviews(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    df = reviews_frame(db, start, end)
    negative = (df[df["sentiment"] == "neg"]
                .sort_values("created_at", ascending=False).head(20))
    return {"range": {"start": str(start), "end": str(end)},
            "summary": summarize_reviews(df),
            "negative_recent": df_records(negative[["dish_name", "rating", "content", "created_at"]])}


def nutrition(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    df = items_frame(db, start, end)
    base = dish_base(db)[["dish_id", "category"]]
    nut = pd.read_sql(select(Dish.id.label("dish_id"), Dish.nutrition_json), db.bind)
    nut = pd.concat([nut[["dish_id"]], nut["nutrition_json"].apply(pd.Series)], axis=1)
    merged = (df.merge(base, on="dish_id")
              .merge(nut[["dish_id", "calories", "protein_g", "fat_g", "carbs_g"]], on="dish_id"))
    summary = weighted_nutrition(merged)
    cat = merged.groupby("category")["amount"].sum().sort_values(ascending=False)
    total = float(cat.sum())
    share = [{"category": k, "revenue": round(float(v), 2),
              "share": round(float(v) / total, 4)} for k, v in cat.items()] if total else []
    light = next((s["share"] for s in share if s["category"] == "轻食"), 0.0)
    return {"range": {"start": str(start), "end": str(end)},
            "summary": summary, "category_share": share, "light_share": light}