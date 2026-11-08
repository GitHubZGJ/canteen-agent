"""查询共用：日期区间解析（默认锚定数据最大日期）与方言中立的时间过滤。"""
import json
from datetime import date, datetime, time, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ERR_PARAM, BizException
from app.models import Order

DEFAULT_WINDOW_DAYS = 30


def df_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame → JSON 安全的字典列表（numpy 类型与 NaN 统一处理）。"""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def resolve_range(db: Session, start: date | None, end: date | None) -> tuple[date, date]:
    if start and end and start > end:
        raise BizException(ERR_PARAM, "开始日期不能晚于结束日期")
    if end is None:
        max_date = db.scalar(select(func.max(func.date(Order.dining_time))))
        if max_date is None:
            raise BizException(ERR_PARAM, "暂无经营数据，请先生成或导入数据")
        end = date.fromisoformat(str(max_date))
    if start is None:
        start = end - timedelta(days=DEFAULT_WINDOW_DAYS - 1)
    return start, end


def datetime_range(column, start: date, end: date) -> tuple:
    """左闭右开区间，避免各数据库 date() 方言差异。"""
    lo = datetime.combine(start, time.min)
    hi = datetime.combine(end + timedelta(days=1), time.min)
    return (column >= lo, column < hi)


def slot_of_hour(hour: int) -> str:
    """就餐时段口径：早 7～10、午 11～14、晚 17～20，其余归其他。"""
    if 7 <= hour < 10:
        return "breakfast"
    if 11 <= hour < 14:
        return "lunch"
    if 17 <= hour < 20:
        return "dinner"
    return "other"


def data_max_date(db: Session) -> date:
    m = db.scalar(select(func.max(func.date(Order.dining_time))))
    if m is None:
        raise BizException(ERR_PARAM, "暂无经营数据，请先生成或导入数据")
    return date.fromisoformat(str(m))