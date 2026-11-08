"""建议工单状态机与效果归因。

状态迁移：draft → approved / rejected；approved → in_progress；
in_progress → evaluating → closed（评估一次完成两步并落效果）。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ERR_PARAM, BizException
from app.models import OperationLog, Suggestion, SuggestionEffect, SuggestionEvent, User
from app.services import dashboard_service
from app.services.common import data_max_date

STATUS_LABELS = {"draft": "待审批", "approved": "已采纳", "rejected": "已驳回",
                 "in_progress": "执行中", "evaluating": "评估中", "closed": "已闭环"}
TRANSITIONS = {
    "approve": ("draft", "approved"),
    "reject": ("draft", "rejected"),
    "execute": ("approved", "in_progress"),
}
EFFECT_METRICS = ("revenue", "orders", "avg_value", "gross_margin", "waste_rate", "satisfaction")


def _get(db: Session, suggestion_id: int) -> Suggestion:
    suggestion = db.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise BizException(1002, "建议工单不存在", http_status=404)
    return suggestion


def _event(db: Session, suggestion: Suggestion, from_status: str, to_status: str,
           operator: int, note: str = "") -> None:
    db.add(SuggestionEvent(suggestion_id=suggestion.id, from_status=from_status,
                           to_status=to_status, operator=operator, note=note))


def _log(db: Session, user_id: int, action: str, target: str, detail: str = "") -> None:
    db.add(OperationLog(user_id=user_id, action=action, target=target, detail=detail))


def _username_map(db: Session) -> dict[int, str]:
    return dict(db.execute(select(User.id, User.username)).all())


def serialize(suggestion: Suggestion, names: dict[int, str] | None = None) -> dict:
    names = names or {}
    return {
        "id": suggestion.id, "type": suggestion.type, "title": suggestion.title,
        "content": suggestion.content_json, "status": suggestion.status,
        "status_label": STATUS_LABELS.get(suggestion.status, suggestion.status),
        "created_by": suggestion.created_by,
        "created_by_name": names.get(suggestion.created_by, ""),
        "reviewed_by": suggestion.reviewed_by,
        "reviewed_by_name": names.get(suggestion.reviewed_by, "") if suggestion.reviewed_by else "",
        "reviewed_at": str(suggestion.reviewed_at) if suggestion.reviewed_at else None,
        "executed_at": str(suggestion.executed_at) if suggestion.executed_at else None,
        "evaluate_after_days": suggestion.evaluate_after_days,
        "created_at": str(suggestion.created_at),
    }


def create_suggestion(db: Session, user: User, type_: str, title: str,
                      content: dict | None, run_id: int | None = None) -> dict:
    suggestion = Suggestion(type=type_, title=title, content_json=content or {},
                            created_by=user.id, run_id=run_id)
    db.add(suggestion)
    db.flush()
    _event(db, suggestion, "new", "draft", user.id, "创建工单")
    _log(db, user.id, "suggestion.create", f"suggestion:{suggestion.id}", title)
    db.commit()
    return serialize(suggestion, _username_map(db))


def list_suggestions(db: Session, status: str | None, page: int, page_size: int) -> dict:
    stmt = select(Suggestion)
    if status:
        stmt = stmt.where(Suggestion.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Suggestion.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    names = _username_map(db)
    return {"total": total, "items": [serialize(s, names) for s in rows]}


def detail(db: Session, suggestion_id: int) -> dict:
    suggestion = _get(db, suggestion_id)
    names = _username_map(db)
    events = db.execute(
        select(SuggestionEvent).where(SuggestionEvent.suggestion_id == suggestion_id)
        .order_by(SuggestionEvent.id)
    ).scalars().all()
    effects = db.execute(
        select(SuggestionEffect).where(SuggestionEffect.suggestion_id == suggestion_id)
        .order_by(SuggestionEffect.id)
    ).scalars().all()
    return {
        **serialize(suggestion, names),
        "events": [{"from": e.from_status, "to": e.to_status,
                    "from_label": STATUS_LABELS.get(e.from_status, e.from_status),
                    "to_label": STATUS_LABELS.get(e.to_status, e.to_status),
                    "operator": e.operator, "operator_name": names.get(e.operator, ""),
                    "note": e.note, "created_at": str(e.created_at)} for e in events],
        "effects": [{"metric": e.metric, "before": e.before_value,
                     "after": e.after_value, "delta": e.delta,
                     "evaluated_at": str(e.evaluated_at)} for e in effects],
    }


def review(db: Session, suggestion_id: int, user: User, approve: bool, note: str) -> dict:
    suggestion = _get(db, suggestion_id)
    action = "approve" if approve else "reject"
    src, dst = TRANSITIONS[action]
    if suggestion.status != src:
        raise BizException(ERR_PARAM, f"状态不允许：当前{STATUS_LABELS[suggestion.status]}，无法{'采纳' if approve else '驳回'}")
    _event(db, suggestion, src, dst, user.id, note)
    suggestion.status = dst
    suggestion.reviewed_by = user.id
    suggestion.reviewed_at = datetime.now()
    _log(db, user.id, f"suggestion.{action}", f"suggestion:{suggestion.id}", note)
    db.commit()
    return detail(db, suggestion_id)


def execute(db: Session, suggestion_id: int, user: User, note: str) -> dict:
    suggestion = _get(db, suggestion_id)
    src, dst = TRANSITIONS["execute"]
    if suggestion.status != src:
        raise BizException(ERR_PARAM, f"状态不允许：当前{STATUS_LABELS[suggestion.status]}，无法执行")
    _event(db, suggestion, src, dst, user.id, note)
    suggestion.status = dst
    suggestion.executed_at = datetime.now()
    _log(db, user.id, "suggestion.execute", f"suggestion:{suggestion.id}", note)
    db.commit()
    return detail(db, suggestion_id)


def evaluate(db: Session, suggestion_id: int, user: User, note: str) -> dict:
    suggestion = _get(db, suggestion_id)
    if suggestion.status != "in_progress" or suggestion.executed_at is None:
        raise BizException(ERR_PARAM,
                           f"状态不允许：当前{STATUS_LABELS[suggestion.status]}，无法评估")
    executed_day = suggestion.executed_at.date()
    last_data_day = data_max_date(db)
    # 数据可能滞后于执行时间：此时评估窗口锚定数据最新日期，并在复盘里注明
    lagged = executed_day > last_data_day
    if lagged:
        after_end = last_data_day
        after_start = after_end - timedelta(days=suggestion.evaluate_after_days - 1)
    else:
        after_end = min(last_data_day, executed_day + timedelta(days=suggestion.evaluate_after_days - 1))
        after_start = executed_day
    after_days = (after_end - after_start).days + 1
    before_end = after_start - timedelta(days=1)
    before_start = before_end - timedelta(days=after_days - 1)

    _event(db, suggestion, "in_progress", "evaluating", user.id, "开始效果评估")
    suggestion.status = "evaluating"
    before = dashboard_service.kpi_range(db, before_start, before_end)
    after = dashboard_service.kpi_range(db, after_start, after_end)
    saved = 0
    for metric in EFFECT_METRICS:
        b, a = before.get(metric), after.get(metric)
        if b is None or a is None:
            continue
        db.add(SuggestionEffect(suggestion_id=suggestion.id, metric=metric,
                                before_value=float(b), after_value=float(a),
                                delta=round(float(a) - float(b), 4)))
        saved += 1
    lag_note = f"数据滞后于执行时间，评估窗口锚定数据最新日期（{last_data_day}）。" if lagged else ""
    window_note = (f"评估窗口 {after_days} 天（{before_start}～{before_end} vs "
                   f"{after_start}～{after_end}），前后对比，非严格因果。{lag_note}{note}".strip())
    _event(db, suggestion, "evaluating", "closed", user.id, window_note)
    suggestion.status = "closed"
    _log(db, user.id, "suggestion.evaluate", f"suggestion:{suggestion.id}", window_note)
    db.commit()
    return {**detail(db, suggestion_id), "effect_count": saved, "window_days": after_days}