"""经营事实：订单、订单明细、评价、浪费记录。"""
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True)
    canteen_id: Mapped[int] = mapped_column(ForeignKey("canteen.id"))
    stall_id: Mapped[int] = mapped_column(ForeignKey("stall.id"))
    channel: Mapped[str] = mapped_column(String(16))  # dine_in / takeout
    dining_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    people_count: Mapped[int] = mapped_column(Integer, default=1)


class OrderItem(Base):
    __tablename__ = "order_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dish.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))


class Review(Base):
    __tablename__ = "review"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dish.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1～5
    content: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    sentiment: Mapped[str] = mapped_column(String(8))  # pos / neu / neg
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WasteRecord(Base):
    __tablename__ = "waste_record"
    __table_args__ = (Index("ix_waste_stall_date", "stall_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stall_id: Mapped[int] = mapped_column(ForeignKey("stall.id"))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dish.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    prepared_qty: Mapped[int] = mapped_column(Integer)
    sold_qty: Mapped[int] = mapped_column(Integer)
    wasted_qty: Mapped[int] = mapped_column(Integer)
    waste_reason: Mapped[str] = mapped_column(String(32), default="")