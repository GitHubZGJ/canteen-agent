"""预测与优化运行的入参。"""
from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    dish_id: int | None = None
    horizon: int = Field(14, ge=7, le=28)
    safety_factor: float = Field(1.1, ge=1.0, le=1.5)


class OptimizationRequest(BaseModel):
    weights: dict[str, float] | None = None
    protected: list[int] = Field(default_factory=list)
    period_days: int = Field(30, ge=7, le=180)