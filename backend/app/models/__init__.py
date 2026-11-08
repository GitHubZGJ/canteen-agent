"""导入全部模型，保证 Base.metadata 完整（Alembic  autogenerate 依赖）。"""
from app.models.agent import AgentMessage, AgentSession, ToolCallLog
from app.models.analysis import ForecastResult, ForecastRun, OptimizationRun
from app.models.canteen import Canteen, Dish, Stall
from app.models.order import Order, OrderItem, Review, WasteRecord
from app.models.suggestion import Suggestion, SuggestionEffect, SuggestionEvent
from app.models.system import OperationLog, Report
from app.models.user import User

__all__ = [
    "AgentMessage",
    "AgentSession",
    "Canteen",
    "Dish",
    "ForecastResult",
    "ForecastRun",
    "OperationLog",
    "OptimizationRun",
    "Order",
    "OrderItem",
    "Report",
    "Review",
    "Stall",
    "Suggestion",
    "SuggestionEffect",
    "SuggestionEvent",
    "ToolCallLog",
    "User",
    "WasteRecord",
]