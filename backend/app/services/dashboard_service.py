"""看板服务：KPI、趋势、排行、时段热力。"""
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.analytics.metrics import compute_kpis, with_delta
from app.models import Dish, Order, OrderItem, Review, Stall, WasteRecord
from app.services.common import datetime_range, resolve_range, slot_of_hour
from app.services.frames import items_frame

SLOT_ORDER = [("breakfast", "早餐"), ("lunch", "午餐"), ("dinner", "晚餐"), ("other", "其他")]
WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _kpi_sums(db: Session, start: date, end: date) -> dict:
    lo, hi = datetime_range(Order.dining_time, start, end)
    revenue, cost_total = db.execute(
        select(func.coalesce(func.sum(OrderItem.amount), 0.0),
               func.coalesce(func.sum(OrderItem.quantity * Dish.cost), 0.0))
        .join(Order, OrderItem.order_id == Order.id)
        .join(Dish, OrderItem.dish_id == Dish.id)
        .where(lo, hi)
    ).one()
    order_count = db.scalar(select(func.count(Order.id)).where(lo, hi))
    prepared, wasted = db.execute(
        select(func.coalesce(func.sum(WasteRecord.prepared_qty), 0),
               func.coalesce(func.sum(WasteRecord.wasted_qty), 0))
        .where(WasteRecord.date >= start, WasteRecord.date <= end)
    ).one()
    rlo, rhi = datetime_range(Review.created_at, start, end)
    rating_sum, rating_count = db.execute(
        select(func.coalesce(func.sum(Review.rating), 0.0), func.count(Review.id))
        .where(rlo, rhi)
    ).one()
    return {
        "revenue": float(revenue), "order_count": int(order_count),
        "cost_total": float(cost_total), "prepared": int(prepared), "wasted": int(wasted),
        "rating_sum": float(rating_sum), "rating_count": int(rating_count),
    }


def kpi_range(db: Session, start: date, end: date) -> dict:
    """指定区间的 KPI 口径值，供效果归因等领域模块复用。"""
    return compute_kpis(**_kpi_sums(db, start, end))


def overview(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    current = compute_kpis(**_kpi_sums(db, start, end))
    span = (end - start).days
    previous = compute_kpis(**_kpi_sums(db, start - timedelta(days=span + 1),
                                        start - timedelta(days=1)))
    df = items_frame(db, start, end)
    slots = []
    if len(df):
        df["slot"] = df["dining_time"].dt.hour.map(slot_of_hour)
        grouped = df.groupby("slot").agg(orders=("order_id", "nunique"),
                                         revenue=("amount", "sum"))
        for key, label in SLOT_ORDER:
            row = grouped.loc[key] if key in grouped.index else None
            slots.append({"slot": key, "label": label,
                          "orders": int(row["orders"]) if row is not None else 0,
                          "revenue": round(float(row["revenue"]), 2) if row is not None else 0.0})
    else:
        slots = [{"slot": k, "label": lb, "orders": 0, "revenue": 0.0} for k, lb in SLOT_ORDER]
    return {"range": {"start": str(start), "end": str(end)},
            "kpis": with_delta(current, previous), "slots": slots}


def trend(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    df = items_frame(db, start, end)
    all_dates = pd.date_range(start, end).date
    if len(df):
        df["d"] = df["dining_time"].dt.date
        grouped = df.groupby("d").agg(revenue=("amount", "sum"),
                                      orders=("order_id", "nunique"))
        grouped = grouped.reindex(all_dates, fill_value=0)
    else:
        grouped = pd.DataFrame({"revenue": 0.0, "orders": 0}, index=all_dates)
    items = [{"date": str(d), "revenue": round(float(row["revenue"]), 2),
              "orders": int(row["orders"]),
              "avg_value": round(float(row["revenue"]) / int(row["orders"]), 2)
              if row["orders"] else 0.0}
             for d, row in grouped.iterrows()]
    return {"range": {"start": str(start), "end": str(end)}, "items": items}


def ranking(db: Session, start: date | None, end: date | None,
            scope: str = "stall", limit: int = 10) -> dict:
    start, end = resolve_range(db, start, end)
    lo, hi = datetime_range(Order.dining_time, start, end)
    entity = Stall if scope == "stall" else Dish
    join_cond = Order.stall_id == Stall.id if scope == "stall" else OrderItem.dish_id == Dish.id
    stmt = (
        select(entity.id, entity.name,
               func.sum(OrderItem.amount).label("revenue"),
               func.sum(OrderItem.quantity).label("quantity"))
        .join(Order, OrderItem.order_id == Order.id)
        .join(entity, join_cond)
        .where(lo, hi)
        .group_by(entity.id, entity.name)
        .order_by(desc("revenue"))
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return {"range": {"start": str(start), "end": str(end)}, "scope": scope,
            "items": [{"id": r.id, "name": r.name, "revenue": round(float(r.revenue), 2),
                       "quantity": int(r.quantity)} for r in rows]}


def heatmap(db: Session, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    df = items_frame(db, start, end)
    if len(df):
        df["weekday"] = df["dining_time"].dt.dayofweek
        df["hour"] = df["dining_time"].dt.hour
        counts = df.groupby(["weekday", "hour"])["order_id"].nunique()
        hours = sorted(df["hour"].unique().tolist())
        data = [[hours.index(int(h)), int(w), int(c)] for (w, h), c in counts.items()]
    else:
        hours, data = list(range(7, 20)), []
    return {"range": {"start": str(start), "end": str(end)},
            "days": WEEKDAY_LABELS, "hours": hours, "data": data}