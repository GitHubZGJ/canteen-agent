"""M2 验收验证：真实库上 API 数字与独立 raw SQL 对照 + 四象限/预警全量复核。

退出码：0 全部通过；1 存在失败项。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import engine
from app.main import app

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"（{detail}）" if detail else ""))


def sql_rows(sql: str, **params) -> list:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).fetchall()


def sql_scalar(sql: str, **params):
    return sql_rows(sql, **params)[0][0]


def main() -> None:
    with TestClient(app) as client:
        token = client.post("/api/auth/login",
                            json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
        client.headers["Authorization"] = f"Bearer {token}"

        ov = client.get("/api/dashboard/overview").json()["data"]
        start, end = ov["range"]["start"], ov["range"]["end"]
        lo, hi = f"{start} 00:00:00", f"{end} 23:59:59"
        kpis = ov["kpis"]

        revenue = sql_scalar("""
            SELECT SUM(oi.amount) FROM order_item oi JOIN orders o ON oi.order_id=o.id
            WHERE o.dining_time BETWEEN :lo AND :hi
        """, lo=lo, hi=hi)
        orders = sql_scalar("SELECT COUNT(*) FROM orders WHERE dining_time BETWEEN :lo AND :hi",
                            lo=lo, hi=hi)
        cost = sql_scalar("""
            SELECT SUM(oi.quantity*d.cost) FROM order_item oi
            JOIN orders o ON oi.order_id=o.id JOIN dish d ON oi.dish_id=d.id
            WHERE o.dining_time BETWEEN :lo AND :hi
        """, lo=lo, hi=hi)
        check("看板营收与 raw SQL 一致", kpis["revenue"]["value"] == round(float(revenue), 2),
              f"区间 {start}～{end}，营收 {kpis['revenue']['value']}")
        check("看板订单数一致", kpis["orders"]["value"] == orders)
        check("看板毛利率一致",
              kpis["gross_margin"]["value"] == round((float(revenue) - float(cost)) / float(revenue), 4))
        prepared = sql_scalar("SELECT SUM(prepared_qty) FROM waste_record WHERE date BETWEEN :s AND :e",
                              s=start, e=end)
        wasted = sql_scalar("SELECT SUM(wasted_qty) FROM waste_record WHERE date BETWEEN :s AND :e",
                            s=start, e=end)
        check("看板浪费率一致", kpis["waste_rate"]["value"] == round(wasted / prepared, 4))

        trend = client.get("/api/dashboard/trend").json()["data"]["items"]
        check("趋势合计等于看板", round(sum(t["revenue"] for t in trend), 2) == kpis["revenue"]["value"]
              and sum(t["orders"] for t in trend) == kpis["orders"]["value"])

        top = client.get("/api/dashboard/ranking", params={"scope": "stall", "limit": 1}).json()["data"]["items"][0]
        row = sql_rows("""
            SELECT s.name, SUM(oi.amount) rev FROM order_item oi
            JOIN orders o ON oi.order_id=o.id JOIN stall s ON o.stall_id=s.id
            WHERE o.dining_time BETWEEN :lo AND :hi
            GROUP BY s.id ORDER BY rev DESC LIMIT 1
        """, lo=lo, hi=hi)[0]
        check("档口排行第一与 raw SQL 一致", top["name"] == row[0]
              and top["revenue"] == round(float(row[1]), 2))

        pf = client.get("/api/analysis/portfolio").json()["data"]
        dishes = pf["dishes"]
        qm, mm = pf["thresholds"]["qty_median"], pf["thresholds"]["margin_median"]
        ok_quad = all(
            d["quadrant"] == ("明星" if d["quantity"] >= qm and d["margin_rate"] >= mm
                              else "金牛" if d["margin_rate"] >= mm
                              else "问题" if d["quantity"] >= qm else "瘦狗")
            for d in dishes)
        check("四象限 120 菜品全量判定正确", len(dishes) == 120 and ok_quad)

        # 滞销集合独立复核：raw SQL 取每菜品每日销量与档口日均值
        daily = sql_rows("""
            SELECT oi.dish_id, date(o.dining_time) d, SUM(oi.quantity) q
            FROM order_item oi JOIN orders o ON oi.order_id=o.id
            WHERE o.dining_time BETWEEN :lo AND :hi GROUP BY oi.dish_id, d
        """, lo=lo, hi=hi)
        import collections
        qty = collections.defaultdict(dict)
        for dish_id, d, q in daily:
            qty[dish_id][d] = q
        stall_of = {d["dish_id"]: d["stall_id"] for d in dishes}
        stall_total = collections.defaultdict(lambda: collections.defaultdict(int))
        for dish_id, per_day in qty.items():
            for d, q in per_day.items():
                stall_total[stall_of[dish_id]][d] += q
        last7 = sorted({d for per_day in qty.values() for d in per_day})[-7:]
        expected_slow = set()
        for d in dishes:
            dish_id, sid = d["dish_id"], d["stall_id"]
            if all(qty[dish_id].get(day, 0) < 0.2 * stall_total[sid][day] / 15 for day in last7):
                expected_slow.add(dish_id)
        api_slow = {s["dish_id"] for s in pf["slow_movers"]}
        check("滞销预警集合与独立计算一致", api_slow == expected_slow,
              f"预警 {len(api_slow)} 个")

        w = client.get("/api/analysis/waste").json()["data"]
        check("浪费总量一致", w["totals"]["prepared"] == prepared and w["totals"]["wasted"] == wasted)
        check("浪费预警阈值正确",
              all(a["waste_rate"] > 0.15 and a["prepared"] >= 50 for a in w["alerts"]),
              f"预警 {len(w['alerts'])} 个")
        # 领域合理性：整体浪费率应在正常经营区间，预警应有区分度而非全量报警
        check("整体浪费率落在 3%～20% 合理区间", 0.03 <= w["totals"]["rate"] <= 0.20,
              f"rate={w['totals']['rate']}")
        check("浪费预警有区分度（1～60 个）", 1 <= len(w["alerts"]) <= 60)
        check("演示数据存在滞销预警", len(pf["slow_movers"]) >= 1)

        rv = client.get("/api/analysis/reviews").json()["data"]
        count = sql_scalar("SELECT COUNT(*) FROM review WHERE created_at BETWEEN :lo AND :hi",
                           lo=lo, hi=hi)
        check("评价数一致", rv["summary"]["count"] == count)

        nu = client.get("/api/analysis/nutrition").json()["data"]
        sold = sql_scalar("""
            SELECT SUM(oi.quantity) FROM order_item oi JOIN orders o ON oi.order_id=o.id
            WHERE o.dining_time BETWEEN :lo AND :hi
        """, lo=lo, hi=hi)
        check("营养加权销量一致", nu["summary"]["sold_qty"] == sold)

        r = client.get("/api/dashboard/overview", params={"start": end, "end": start})
        check("非法区间拒绝且 msg 明确", r.status_code == 400 and r.json()["code"] == 1001
              and r.json()["msg"] == "开始日期不能晚于结束日期")
        r = client.get("/api/dishes/99999/analysis")
        check("不存在菜品 404 且 msg 明确", r.status_code == 404 and r.json()["msg"] == "菜品不存在")

    failed = RESULTS.count(False)
    print(f"\n合计 {len(RESULTS)} 项，失败 {failed} 项")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()