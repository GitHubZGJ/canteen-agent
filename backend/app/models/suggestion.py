"""决策闭环：建议工单、状态流转事件、效果归因。

状态机：draft → approved / rejected → in_progress → evaluating → closed
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# 工单状态常量，服务层状态机据此校验迁移
SUGGESTION_STATUSES = ("draft", "approved", "rejected", "in_progress", "evaluating", "closed")


class Suggestion(Base):
    __tablename__ = "suggestion"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("optimization_run.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(32))  # menu_change / forecast_adjust / promotion / other
    title: Mapped[str] = mapped_column(String(128))
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("user.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evaluate_after_days: Mapped[int] = mapped_column(Integer, default=14)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SuggestionEvent(Base):
    __tablename__ = "suggestion_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    suggestion_id: Mapped[int] = mapped_column(ForeignKey("suggestion.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    operator: Mapped[int] = mapped_column(ForeignKey("user.id"))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SuggestionEffect(Base):
    __tablename__ = "suggestion_effect"

    id: Mapped[int] = mapped_column(primary_key=True)
    suggestion_id: Mapped[int] = mapped_column(ForeignKey("suggestion.id"), index=True)
    metric: Mapped[str] = mapped_column(String(32))
    before_value: Mapped[float] = mapped_column(Float)
    after_value: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())