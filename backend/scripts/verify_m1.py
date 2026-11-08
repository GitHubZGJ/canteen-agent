"""M1 验收验证：表结构、数据规模、认证接口（负向用例连 msg 一起断言）。

先启动过应用或让本脚本触发 lifespan（迁移 + 播种幂等），再逐项检查。
退出码：0 全部通过；1 存在失败项。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.core.database import SessionLocal, engine
from app.main import app
from app.models import Canteen, Dish, Order, OrderItem, Review, Stall, WasteRecord

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"（{detail}）" if detail else ""))


def main() -> None:
    with TestClient(app) as client:  # 触发 lifespan：迁移 + 默认用户播种
        names = [n for n in inspect(engine).get_table_names() if n != "alembic_version"]
        check("19 张业务表齐全", len(names) == 19, f"实际 {len(names)}")

        with SessionLocal() as db:
            counts = {m.__tablename__: db.query(m).count() for m in
                      (Canteen, Stall, Dish, Order, OrderItem, Review, WasteRecord)}
        check("2 食堂 8 档口 120 菜品",
              counts["canteen"] == 2 and counts["stall"] == 8 and counts["dish"] == 120,
              str(counts))
        check("订单规模约 25 万", counts["orders"] >= 200000, f"orders={counts['orders']}")
        check("明细不少于订单", counts["order_item"] >= counts["orders"])
        check("评价与浪费记录非空", counts["review"] > 1000 and counts["waste_record"] > 0,
              f"review={counts['review']} waste={counts['waste_record']}")

        r = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@123"})
        body = r.json()
        check("管理员登录拿 JWT", r.status_code == 200 and body["code"] == 0
              and bool(body["data"]["token"]))
        token = body["data"]["token"]

        r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        body = r.json()
        check("错误密码拒绝且 msg 明确", r.status_code == 400 and body["code"] == 3001
              and body["msg"] == "用户名或密码错误")

        r = client.get("/api/auth/me")
        check("无 token 拒绝", r.status_code == 401 and r.json()["code"] == 2001)

        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        check("带 token 取当前用户", r.status_code == 200
              and r.json()["data"]["username"] == "admin")

        r = client.get("/api/health")
        check("健康检查", r.status_code == 200 and r.json()["data"]["status"] == "ok")

    failed = RESULTS.count(False)
    print(f"\n合计 {len(RESULTS)} 项，失败 {failed} 项")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()