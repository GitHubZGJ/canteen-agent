"""经营周报：汇总指标、排行、预警与工单进展，生成 Markdown 留痕。"""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Report, Suggestion
from app.services import analysis_service, dashboard_service
from app.services.common import data_max_date
from app.services.suggestion_service import STATUS_LABELS


def generate_weekly(db: Session, end: date | None = None, days: int = 7) -> dict:
    end = end or data_max_date(db)
    start = end - timedelta(days=days - 1)
    ov = dashboard_service.overview(db, start, end)
    rank = dashboard_service.ranking(db, start, end, "stall", 3)["items"]
    pf = analysis_service.portfolio(db, start, end)
    waste = analysis_service.waste(db, start, end)
    reviews = analysis_service.reviews(db, start, end)
    status_counts = dict(
        db.execute(select(Suggestion.status, func.count(Suggestion.id))
                   .group_by(Suggestion.status)).all()
    )
    k = {key: v["value"] for key, v in ov["kpis"].items()}
    slow = pf["slow_movers"][:3]
    alerts = waste["alerts"][:3]
    negative = reviews["negative_recent"][:3]
    satisfaction = k["satisfaction"] if k["satisfaction"] is not None else "-"
    lines = [
        f"# 食堂经营周报（{start} ～ {end}）",
        "",
        "## 核心指标",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 营收 | ¥{k['revenue']:,} |",
        f"| 订单数 | {k['orders']:,} |",
        f"| 客单价 | ¥{k['avg_value']} |",
        f"| 毛利率 | {k['gross_margin'] * 100:.1f}% |",
        f"| 浪费率 | {k['waste_rate'] * 100:.1f}% |",
        f"| 满意度 | {satisfaction} |",
        "",
        "## 档口营收前三",
        "",
        *[f"{i}. {r['name']}：¥{r['revenue']:,}" for i, r in enumerate(rank, 1)],
        "",
        "## 预警",
        "",
        f"- 滞销菜品 {len(pf['slow_movers'])} 个"
        + (f"（{'、'.join(s['name'] for s in slow)} 等）" if slow else ""),
        f"- 浪费预警 {len(waste['alerts'])} 个菜品浪费率超 15%"
        + (f"（{'、'.join(a['name'] for a in alerts)} 等）" if alerts else ""),
        "",
        "## 工单进展",
        "",
        "、".join(f"{STATUS_LABELS.get(s, s)} {c} 个" for s, c in status_counts.items()) or "暂无工单",
        "",
        "## 负面评价摘录",
        "",
        *[f"- {n['dish_name']}（{n['rating']} 分）：{n['content']}" for n in negative],
        "",
        "> 数据为模拟数据；指标口径见架构文档。",
    ]
    period = f"{start}~{end}"
    report = Report(type="weekly", period=period, content_md="\n".join(lines))
    db.add(report)
    db.commit()
    return {"id": report.id, "period": period, "content_md": report.content_md}


def list_reports(db: Session, limit: int = 20) -> list[dict]:
    rows = db.execute(select(Report).order_by(Report.id.desc()).limit(limit)).scalars().all()
    return [{"id": r.id, "type": r.type, "period": r.period,
             "created_at": str(r.created_at)} for r in rows]


def get_report(db: Session, report_id: int) -> dict:
    from app.core.exceptions import BizException

    report = db.get(Report, report_id)
    if report is None:
        raise BizException(1002, "报告不存在", http_status=404)
    return {"id": report.id, "type": report.type, "period": report.period,
            "content_md": report.content_md, "created_at": str(report.created_at)}