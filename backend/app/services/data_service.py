"""数据管理：模拟数据生成与三类 CSV 导入（列校验 + 错误行报告）。

模板是 app/data_templates 下的单一份 CSV，接口原样下发；
导入支持 UTF-8 与 GB18030（Excel 常见），逐行校验，合法行入库、错误行回报。
"""
import csv
import io
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ERR_PARAM, BizException
from app.models import Canteen, Dish, Order, OrderItem, Review, Stall

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data_templates"
KINDS = ("dishes", "orders", "reviews")
REQUIRED = {
    "dishes": {"stall_name", "name", "price", "cost"},
    "orders": {"order_no", "stall_name", "dish_name", "quantity", "dining_time"},
    "reviews": {"stall_name", "dish_name", "rating"},
}
MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024


def template_csv(kind: str) -> str:
    if kind not in KINDS:
        raise BizException(ERR_PARAM, f"未知模板类型：{kind}")
    return (TEMPLATE_DIR / f"{kind}.csv").read_text(encoding="utf-8")


def generate_simulated(db: Session, days: int, seed: int,
                       end_date: date | None, reset: bool) -> dict:
    from scripts.generate_data import generate, reset_business_data

    existing = db.scalar(select(func.count(Canteen.id)))
    if existing and not reset:
        raise BizException(ERR_PARAM, "已存在经营数据；如需重建请勾选重置")
    if reset:
        reset_business_data(db)
    return generate(db, days=days, seed=seed, end_date=end_date or date.today())


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise BizException(ERR_PARAM, "CSV 编码无法识别，请使用 UTF-8 或 GB18030")


def _to_float(value: str | None, field: str) -> float:
    try:
        return float((value or "").strip())
    except ValueError:
        raise BizException(ERR_PARAM, f"字段 {field} 不是合法数字：{value!r}")


def _to_int(value: str | None, field: str, minimum: int = 1) -> int:
    try:
        number = int((value or "").strip())
    except ValueError:
        raise BizException(ERR_PARAM, f"字段 {field} 不是合法整数：{value!r}")
    if number < minimum:
        raise BizException(ERR_PARAM, f"字段 {field} 不能小于 {minimum}")
    return number


def _split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    for sep in ("，", ","):
        value = value.replace(sep, "|")
    return [t.strip() for t in value.split("|") if t.strip()]


def _parse_dt(value: str | None, field: str) -> datetime:
    text = (value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise BizException(ERR_PARAM, f"字段 {field} 时间格式应为 YYYY-MM-DD HH:MM:SS")


def _result(imported: int, errors: list[dict]) -> dict:
    return {"total": imported + len(errors), "imported": imported,
            "error_count": len(errors), "errors": errors[:20]}


def _lookups(db: Session) -> tuple[dict, dict]:
    stalls = {s.name: s for s in db.execute(select(Stall)).scalars()}
    dish_rows = db.execute(select(Dish, Stall.name).join(Stall, Dish.stall_id == Stall.id)).all()
    dishes = {(stall_name, dish.name): dish for dish, stall_name in dish_rows}
    return stalls, dishes


def _import_dishes(db: Session, rows: list[dict]) -> dict:
    stalls, _ = _lookups(db)
    existing = set(db.execute(select(Dish.stall_id, Dish.name)).all())
    imported, errors = 0, []
    for line_no, row in enumerate(rows, start=2):
        try:
            stall_name = (row.get("stall_name") or "").strip()
            name = (row.get("name") or "").strip()
            stall = stalls.get(stall_name)
            if stall is None:
                raise BizException(ERR_PARAM, f"档口不存在：{stall_name or '（空）'}")
            if not name:
                raise BizException(ERR_PARAM, "菜品名称为空")
            price = _to_float(row.get("price"), "price")
            cost = _to_float(row.get("cost"), "cost")
            if price <= 0 or cost < 0 or cost >= price:
                raise BizException(ERR_PARAM, "价格或成本不合法（需 0 ≤ 成本 < 价格）")
            if (stall.id, name) in existing:
                raise BizException(ERR_PARAM, f"档口内已存在同名菜品：{name}")
            nutrition = {}
            for key in ("calories", "protein_g", "fat_g", "carbs_g"):
                value = (row.get(key) or "").strip()
                if value:
                    nutrition[key] = _to_float(value, key)
            db.add(Dish(stall_id=stall.id, name=name,
                        category=(row.get("category") or "其他").strip(),
                        price=price, cost=cost, tags=_split_tags(row.get("tags")),
                        nutrition_json=nutrition or {"note": "CSV 导入，营养未提供"}))
            existing.add((stall.id, name))
            imported += 1
        except BizException as exc:
            errors.append({"row": line_no, "msg": exc.msg})
    db.commit()
    return _result(imported, errors)


def _import_orders(db: Session, rows: list[dict]) -> dict:
    stalls, dishes = _lookups(db)
    imported, errors = 0, []
    seen: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        try:
            order_no = (row.get("order_no") or "").strip()
            if not order_no:
                raise BizException(ERR_PARAM, "订单号为空")
            if order_no in seen or db.scalar(select(Order.id).where(Order.order_no == order_no)):
                raise BizException(ERR_PARAM, f"订单号重复：{order_no}")
            stall_name = (row.get("stall_name") or "").strip()
            dish_name = (row.get("dish_name") or "").strip()
            stall = stalls.get(stall_name)
            if stall is None:
                raise BizException(ERR_PARAM, f"档口不存在：{stall_name or '（空）'}")
            dish = dishes.get((stall_name, dish_name))
            if dish is None:
                raise BizException(ERR_PARAM, f"菜品不存在：{stall_name} / {dish_name or '（空）'}")
            quantity = _to_int(row.get("quantity"), "quantity")
            dining_time = _parse_dt(row.get("dining_time"), "dining_time")
            channel = (row.get("channel") or "dine_in").strip()
            if channel not in ("dine_in", "takeout"):
                raise BizException(ERR_PARAM, "channel 只能是 dine_in 或 takeout")
            people = _to_int(row.get("people_count") or "1", "people_count")
            amount = round(float(dish.price) * quantity, 2)
            order = Order(order_no=order_no, canteen_id=stall.canteen_id, stall_id=stall.id,
                          channel=channel, dining_time=dining_time, amount=amount,
                          people_count=min(10, people))
            db.add(order)
            db.flush()
            db.add(OrderItem(order_id=order.id, dish_id=dish.id, quantity=quantity,
                             price=dish.price, amount=amount))
            seen.add(order_no)
            imported += 1
        except BizException as exc:
            errors.append({"row": line_no, "msg": exc.msg})
    db.commit()
    return _result(imported, errors)


def _import_reviews(db: Session, rows: list[dict]) -> dict:
    _, dishes = _lookups(db)
    imported, errors = 0, []
    for line_no, row in enumerate(rows, start=2):
        try:
            stall_name = (row.get("stall_name") or "").strip()
            dish_name = (row.get("dish_name") or "").strip()
            dish = dishes.get((stall_name, dish_name))
            if dish is None:
                raise BizException(ERR_PARAM, f"菜品不存在：{stall_name} / {dish_name or '（空）'}")
            rating = _to_int(row.get("rating"), "rating")
            if rating > 5:
                raise BizException(ERR_PARAM, "rating 应在 1～5")
            created_text = (row.get("created_at") or "").strip()
            db.add(Review(order_id=None, dish_id=dish.id, rating=rating,
                          content=(row.get("content") or "").strip(),
                          tags=_split_tags(row.get("tags")),
                          sentiment="pos" if rating >= 4 else "neu" if rating == 3 else "neg",
                          created_at=_parse_dt(created_text, "created_at") if created_text else datetime.now()))
            imported += 1
        except BizException as exc:
            errors.append({"row": line_no, "msg": exc.msg})
    db.commit()
    return _result(imported, errors)


def import_csv(db: Session, kind: str, raw: bytes) -> dict:
    if kind not in KINDS:
        raise BizException(ERR_PARAM, f"未知导入类型：{kind}")
    if len(raw) > MAX_BYTES:
        raise BizException(ERR_PARAM, "文件超过 5 MB 上限")
    reader = csv.DictReader(io.StringIO(_decode(raw)))
    if not reader.fieldnames:
        raise BizException(ERR_PARAM, "CSV 为空或缺少表头")
    headers = {h.strip() for h in reader.fieldnames if h}
    missing = REQUIRED[kind] - headers
    if missing:
        raise BizException(ERR_PARAM, f"缺少必需列：{'、'.join(sorted(missing))}")
    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise BizException(ERR_PARAM, f"单次最多导入 {MAX_ROWS} 行")
    handlers: dict[str, Callable] = {"dishes": _import_dishes, "orders": _import_orders,
                                     "reviews": _import_reviews}
    return handlers[kind](db, rows)