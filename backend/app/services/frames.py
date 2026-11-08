"""共享查询帧：服务层唯一的 SQL 聚合入口，输出 pandas DataFrame。

时间分组统一在 pandas 内做，规避 SQLite/PostgreSQL 日期函数方言差异。
"""
from datetime import date

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Dish, Order, OrderItem, Review, Stall, WasteRecord
from app.services.common import datetime_range


def items_frame(db: Session, start: date, end: date) -> pd.DataFrame:
    """区间内的订单明细（含就餐时间），供趋势/时段/热力/滞销使用。"""
    lo, hi = datetime_range(Order.dining_time, start, end)
    stmt = (
        select(Order.id.label("order_id"), Order.dining_time,
               OrderItem.dish_id, OrderItem.quantity, OrderItem.amount)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(lo, hi)
    )
    return pd.read_sql(stmt, db.bind)


def dish_base(db: Session) -> pd.DataFrame:
    return pd.read_sql(
        select(Dish.id.label("dish_id"), Dish.name, Dish.category, Dish.price,
               Dish.stall_id, Stall.name.label("stall_name"))
        .join(Stall, Dish.stall_id == Stall.id),
        db.bind,
    )


def dish_sales(db: Session, start: date, end: date) -> pd.DataFrame:
    lo, hi = datetime_range(Order.dining_time, start, end)
    stmt = (
        select(OrderItem.dish_id,
               func.sum(OrderItem.quantity).label("quantity"),
               func.sum(OrderItem.amount).label("revenue"),
               func.sum(OrderItem.quantity * Dish.cost).label("cost_total"))
        .join(Order, OrderItem.order_id == Order.id)
        .join(Dish, OrderItem.dish_id == Dish.id)
        .where(lo, hi)
        .group_by(OrderItem.dish_id)
    )
    return pd.read_sql(stmt, db.bind)


def dish_reviews(db: Session, start: date, end: date) -> pd.DataFrame:
    lo, hi = datetime_range(Review.created_at, start, end)
    stmt = (
        select(Review.dish_id, func.avg(Review.rating).label("avg_rating"),
               func.count(Review.id).label("review_count"))
        .where(lo, hi)
        .group_by(Review.dish_id)
    )
    return pd.read_sql(stmt, db.bind)


def dish_waste(db: Session, start: date, end: date) -> pd.DataFrame:
    stmt = (
        select(WasteRecord.dish_id,
               func.sum(WasteRecord.prepared_qty).label("prepared"),
               func.sum(WasteRecord.wasted_qty).label("wasted"))
        .where(WasteRecord.date >= start, WasteRecord.date <= end)
        .group_by(WasteRecord.dish_id)
    )
    return pd.read_sql(stmt, db.bind)


def reviews_frame(db: Session, start: date, end: date) -> pd.DataFrame:
    lo, hi = datetime_range(Review.created_at, start, end)
    stmt = (
        select(Review.id, Review.dish_id, Review.rating, Review.content,
               Review.tags, Review.sentiment, Review.created_at, Dish.name.label("dish_name"))
        .join(Dish, Review.dish_id == Dish.id)
        .where(lo, hi)
    )
    return pd.read_sql(stmt, db.bind)


def waste_frame(db: Session, start: date, end: date) -> pd.DataFrame:
    stmt = select(WasteRecord).where(WasteRecord.date >= start, WasteRecord.date <= end)
    return pd.read_sql(stmt, db.bind)


def dish_stats_frame(db: Session, start: date, end: date) -> pd.DataFrame:
    """菜品主数据 + 区间销售/评价/浪费聚合；无销售菜品保留并补 0。"""
    df = dish_base(db).merge(dish_sales(db, start, end), on="dish_id", how="left")
    for col in ("quantity", "revenue", "cost_total"):
        df[col] = df[col].fillna(0)
    df["margin_rate"] = ((df["revenue"] - df["cost_total"])
                         / df["revenue"].where(df["revenue"] > 0)).fillna(0.0).round(4)
    df = df.merge(dish_reviews(db, start, end), on="dish_id", how="left")
    df["avg_rating"] = df["avg_rating"].round(2)
    df["review_count"] = df["review_count"].fillna(0).astype(int)
    df = df.merge(dish_waste(db, start, end), on="dish_id", how="left")
    df[["prepared", "wasted"]] = df[["prepared", "wasted"]].fillna(0).astype(int)
    df["waste_rate"] = (df["wasted"]
                        / df["prepared"].where(df["prepared"] > 0)).fillna(0.0).round(4)
    return df