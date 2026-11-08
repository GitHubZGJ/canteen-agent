"""菜品服务：列表（分页筛选）与单品分析。"""
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics.reviews import summarize_reviews
from app.core.exceptions import BizException
from app.models import Dish, Stall
from app.services.common import df_records, resolve_range
from app.services.frames import (
    dish_stats_frame,
    items_frame,
    reviews_frame,
    waste_frame,
)


def list_dishes(db: Session, page: int, page_size: int, stall_id: int | None,
                category: str | None, keyword: str | None,
                start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    df = dish_stats_frame(db, start, end)
    if stall_id is not None:
        df = df[df["stall_id"] == stall_id]
    if category:
        df = df[df["category"] == category]
    if keyword:
        df = df[df["name"].str.contains(keyword, regex=False)]
    df = df.sort_values("revenue", ascending=False)
    total = len(df)
    page_df = df.iloc[(page - 1) * page_size: page * page_size]
    return {"range": {"start": str(start), "end": str(end)},
            "total": total, "items": df_records(page_df)}


def dish_analysis(db: Session, dish_id: int, start: date | None, end: date | None) -> dict:
    start, end = resolve_range(db, start, end)
    dish = db.get(Dish, dish_id)
    if dish is None:
        raise BizException(1002, "菜品不存在", http_status=404)
    stall = db.get(Stall, dish.stall_id)
    all_dates = list(pd.date_range(start, end).date)

    items = items_frame(db, start, end)
    sub = items[items["dish_id"] == dish_id].copy()
    if len(sub):
        sub["d"] = sub["dining_time"].dt.date
        daily = sub.groupby("d").agg(quantity=("quantity", "sum"),
                                     revenue=("amount", "sum"))
        daily = daily.reindex(all_dates, fill_value=0)
    else:
        daily = pd.DataFrame({"quantity": 0, "revenue": 0.0}, index=all_dates)
    trend = [{"date": str(d), "quantity": int(r["quantity"]),
              "revenue": round(float(r["revenue"]), 2)} for d, r in daily.iterrows()]

    rv = reviews_frame(db, start, end)
    rv_sub = rv[rv["dish_id"] == dish_id]
    recent = rv_sub.sort_values("created_at", ascending=False).head(5)

    w = waste_frame(db, start, end)
    w_sub = w[w["dish_id"] == dish_id]
    prepared, wasted = int(w_sub["prepared_qty"].sum()), int(w_sub["wasted_qty"].sum())

    return {
        "range": {"start": str(start), "end": str(end)},
        "dish": {"id": dish.id, "name": dish.name, "category": dish.category,
                 "price": float(dish.price), "stall_name": stall.name if stall else ""},
        "trend": trend,
        "reviews": {"summary": summarize_reviews(rv_sub),
                    "recent": df_records(recent[["rating", "content", "created_at"]])},
        "waste": {"prepared": prepared, "wasted": wasted,
                  "rate": round(wasted / prepared, 4) if prepared else 0.0},
    }