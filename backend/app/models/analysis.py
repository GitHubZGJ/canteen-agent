"""分析结果留痕：预测运行与结果、优化运行。"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ForecastRun(Base):
    __tablename__ = "forecast_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    dish_id: Mapped[int | None] = mapped_column(ForeignKey("dish.id"), nullable=True)
    target_start: Mapped[date] = mapped_column(Date)
    target_end: Mapped[date] = mapped_column(Date)
    model: Mapped[str] = mapped_column(String(32))
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ForecastResult(Base):
    __tablename__ = "forecast_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_run.id"), index=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dish.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(16))  # breakfast / lunch / dinner
    predicted_qty: Mapped[float] = mapped_column(Float)
    lower: Mapped[float] = mapped_column(Float)
    upper: Mapped[float] = mapped_column(Float)


class OptimizationRun(Base):
    __tablename__ = "optimization_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), default="all")
    objectives_json: Mapped[dict] = mapped_column(JSON, default=dict)
    weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())