"""生成器测试：小规模确定性复现 + 数据完整性 + reset 行为。"""
import hashlib
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Canteen, Dish, Order, OrderItem, WasteRecord
from scripts.generate_data import generate, reset_business_data


def make_session(tmp_path, name):
    engine = create_engine(f"sqlite:///{tmp_path.as_posix()}/{name}.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def fingerprint(db):
    """对订单与明细全量行做哈希，验证逐行一致而非仅行数一致。"""
    def row_dict(obj):
        # 只取列值；__dict__ 里的 _sa_instance_state 含内存地址，不可用于哈希
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    h = hashlib.sha256()
    for row in db.execute(select(Order).order_by(Order.id)):
        h.update(repr(row_dict(row[0])).encode())
    for row in db.execute(select(OrderItem).order_by(OrderItem.id)):
        h.update(repr(row_dict(row[0])).encode())
    return h.hexdigest()


def test_deterministic(tmp_path):
    db1 = make_session(tmp_path, "a")
    db2 = make_session(tmp_path, "b")
    c1 = generate(db1, days=7, seed=42, end_date=date(2026, 11, 6))
    c2 = generate(db2, days=7, seed=42, end_date=date(2026, 11, 6))
    assert c1 == c2
    assert c1["dish"] == 120
    assert c1["waste_record"] == 120 * 7
    assert c1["orders"] > 0
    assert c1["order_item"] >= c1["orders"]
    assert fingerprint(db1) == fingerprint(db2)
    db1.close()
    db2.close()


def test_different_seed_differs(tmp_path):
    db1 = make_session(tmp_path, "a")
    db2 = make_session(tmp_path, "b")
    generate(db1, days=7, seed=42, end_date=date(2026, 11, 6))
    generate(db2, days=7, seed=43, end_date=date(2026, 11, 6))
    assert fingerprint(db1) != fingerprint(db2)
    db1.close()
    db2.close()


def test_reset_clears_business_keeps_structure(tmp_path):
    db = make_session(tmp_path, "a")
    generate(db, days=3, seed=42, end_date=date(2026, 11, 6))
    reset_business_data(db)
    assert db.query(Order).count() == 0
    assert db.query(Dish).count() == 0
    assert db.query(Canteen).count() == 0
    assert db.query(WasteRecord).count() == 0
    db.close()