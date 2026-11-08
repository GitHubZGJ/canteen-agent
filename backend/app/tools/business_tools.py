"""智能体业务工具：8 个，读多写一（仅创建建议草稿）。"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.services import (
    analysis_service,
    dashboard_service,
    forecast_service,
    optimization_service,
    report_service,
    suggestion_service,
)
from app.tools.registry import tool


class RangeArgs(BaseModel):
    start: date | None = Field(default=None, description="开始日期 YYYY-MM-DD，缺省为数据最近 30 天")
    end: date | None = Field(default=None, description="结束日期 YYYY-MM-DD，缺省为数据最大日期")


@tool("query_metrics", "查询区间经营指标：营收、订单数、客单价、毛利率、浪费率、满意度，以及早中晚时段分布", RangeArgs)
def query_metrics(db, user, start=None, end=None):
    data = dashboard_service.overview(db, start, end)
    kpis = {k: v["value"] for k, v in data["kpis"].items()}
    return {"range": data["range"], "kpis": kpis, "slots": data["slots"]}


@tool("analyze_portfolio", "菜品组合分析：销量×毛利四象限、ABC 分类、滞销预警（连续 7 天低于档口均值 20%）", RangeArgs)
def analyze_portfolio(db, user, start=None, end=None):
    data = analysis_service.portfolio(db, start, end)
    quadrant_counts: dict[str, int] = {}
    for d in data["dishes"]:
        quadrant_counts[d["quadrant"]] = quadrant_counts.get(d["quadrant"], 0) + 1
    top = sorted(data["dishes"], key=lambda d: d["revenue"], reverse=True)[:3]
    return {"range": data["range"], "quadrant_counts": quadrant_counts,
            "abc_counts": {c: sum(1 for d in data["dishes"] if d["abc"] == c) for c in "ABC"},
            "slow_movers": data["slow_movers"][:5],
            "top_revenue": [{"name": d["name"], "revenue": d["revenue"]} for d in top]}


class ForecastArgs(BaseModel):
    dish_id: int | None = Field(default=None, description="菜品 id；缺省返回最近一次运行摘要")
    horizon: int = Field(default=14, ge=7, le=28, description="回测天数")


@tool("forecast_demand", "备餐量预测：按菜品回测 Holt-Winters 与基线误差并给出备餐建议；不指定菜品时返回最近一次运行摘要", ForecastArgs)
def forecast_demand(db, user, dish_id=None, horizon=14):
    if dish_id is None:
        runs = forecast_service.list_runs(db, limit=1)
        if not runs:
            return {"hint": "尚未发起过预测。请指定菜品 id（可通过菜品接口或分析结论获取）后再回测。"}
        return {"latest_run": runs[0], "hint": "如需重新回测请提供 dish_id。"}
    run = forecast_service.run_forecast(db, dish_id, horizon, 1.1)
    return {"run_id": run["run_id"], "metrics": run["metrics"],
            "fallback_count": run["fallback_count"],
            "total_estimated_saving": run["total_estimated_saving"],
            "prep_suggestions": run["prep_suggestions"]}


class OptimizeArgs(BaseModel):
    weights: dict[str, float] | None = Field(
        default=None, description="权重：margin/satisfaction/nutrition/waste，缺省 0.4/0.3/0.15/0.15")


@tool("optimize_menu", "多目标菜单优化：按毛利、满意度、营养、低浪费加权打分，输出推广/保留/汰换建议", OptimizeArgs)
def optimize_menu(db, user, weights=None):
    run = optimization_service.run_optimization(db, weights, [], 30)
    promoted = [d for d in run["dishes"] if d["action"] == "推广"][:3]
    removed = [d for d in run["dishes"] if d["action"] == "汰换"][:3]
    return {"run_id": run["run_id"], "period": run["period"], "counts": run["counts"],
            "promote_samples": [{"dish_id": d["dish_id"], "name": d["name"],
                                 "score": d["score"]} for d in promoted],
            "remove_samples": [{"dish_id": d["dish_id"], "name": d["name"],
                                "score": d["score"]} for d in removed]}


@tool("analyze_reviews", "评价分析：平均评分、评分分布、情感构成、高频标签与最新负面评价", RangeArgs)
def analyze_reviews(db, user, start=None, end=None):
    data = analysis_service.reviews(db, start, end)
    summary = data["summary"]
    return {"range": data["range"], "count": summary["count"],
            "avg_rating": summary["avg_rating"],
            "rating_dist": summary["rating_dist"],
            "sentiment_dist": summary["sentiment_dist"],
            "top_tags": dict(list(summary["tag_counts"].items())[:8]),
            "negative_recent": data["negative_recent"][:3]}


@tool("detect_waste", "浪费分析：浪费率、预警菜品（浪费率>15% 且备餐≥50）、主要原因与趋势", RangeArgs)
def detect_waste(db, user, start=None, end=None):
    data = analysis_service.waste(db, start, end)
    return {"range": data["range"], "totals": data["totals"],
            "alert_count": len(data["alerts"]),
            "alerts": [{"name": a["name"], "waste_rate": a["waste_rate"],
                        "wasted": a["wasted"]} for a in data["alerts"][:5]],
            "by_reason": data["by_reason"]}


class SuggestionArgs(BaseModel):
    type: Literal["menu_change", "forecast_adjust", "promotion", "other"] = Field(
        description="建议类型：菜单调整/备餐调整/推广/其他")
    title: str = Field(min_length=2, max_length=120, description="建议标题")
    content: dict = Field(default_factory=dict, description="建议内容，如菜品 id、依据与动作")
    run_id: int | None = Field(default=None, description="关联的优化运行 id")


@tool("create_suggestion", "创建建议工单草稿（唯一写操作；需人工审批后才生效）", SuggestionArgs, write=True)
def create_suggestion(db, user, type, title, content, run_id=None):
    data = suggestion_service.create_suggestion(db, user, type, title, content, run_id)
    return {"suggestion_id": data["id"], "status": data["status"],
            "status_label": data["status_label"], "title": data["title"]}


class ReportArgs(BaseModel):
    days: int = Field(default=7, ge=1, le=30, description="统计天数")
    end: date | None = Field(default=None, description="截止日期 YYYY-MM-DD，缺省为数据最大日期")


@tool("generate_report", "生成经营周报：核心指标、排行、预警、工单进展与负面评价摘录", ReportArgs)
def generate_report(db, user, days=7, end=None):
    report = report_service.generate_weekly(db, end, days)
    return {"report_id": report["id"], "period": report["period"],
            "content_md": report["content_md"]}