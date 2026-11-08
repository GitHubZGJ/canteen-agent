"""分析接口集成测试：API 数字与独立 raw SQL 对照，负向用例连 msg 断言。"""
from sqlalchemy import text

RANGE = {"start": "2026-10-24", "end": "2026-11-06"}


def sql_scalar(engine, sql, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def test_overview_matches_raw_sql(client_with_data):
    client, engine = client_with_data
    body = client.get("/api/dashboard/overview", params=RANGE).json()
    assert body["code"] == 0
    kpis = body["data"]["kpis"]
    revenue = sql_scalar(engine, """
        SELECT SUM(oi.amount) FROM order_item oi JOIN orders o ON oi.order_id = o.id
        WHERE o.dining_time >= :lo AND o.dining_time < :hi
    """, lo="2026-10-24 00:00:00", hi="2026-11-07 00:00:00")
    orders = sql_scalar(engine, """
        SELECT COUNT(*) FROM orders
        WHERE dining_time >= :lo AND dining_time < :hi
    """, lo="2026-10-24 00:00:00", hi="2026-11-07 00:00:00")
    assert kpis["revenue"]["value"] == round(float(revenue), 2)
    assert kpis["orders"]["value"] == orders
    assert kpis["avg_value"]["value"] == round(float(revenue) / orders, 2)
    prepared = sql_scalar(engine, "SELECT SUM(prepared_qty) FROM waste_record WHERE date BETWEEN :s AND :e",
                          s=RANGE["start"], e=RANGE["end"])
    wasted = sql_scalar(engine, "SELECT SUM(wasted_qty) FROM waste_record WHERE date BETWEEN :s AND :e",
                        s=RANGE["start"], e=RANGE["end"])
    assert kpis["waste_rate"]["value"] == round(wasted / prepared, 4)


def test_trend_sums_to_overview(client_with_data):
    client, _ = client_with_data
    trend = client.get("/api/dashboard/trend", params=RANGE).json()["data"]["items"]
    overview = client.get("/api/dashboard/overview", params=RANGE).json()["data"]["kpis"]
    assert len(trend) == 14
    assert round(sum(t["revenue"] for t in trend), 2) == overview["revenue"]["value"]
    assert sum(t["orders"] for t in trend) == overview["orders"]["value"]


def test_ranking_matches_raw_sql(client_with_data):
    client, engine = client_with_data
    top = client.get("/api/dashboard/ranking", params={**RANGE, "scope": "stall", "limit": 1}).json()["data"]["items"][0]
    row = None
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT s.name, SUM(oi.amount) AS rev FROM order_item oi
            JOIN orders o ON oi.order_id = o.id JOIN stall s ON o.stall_id = s.id
            WHERE o.dining_time >= :lo AND o.dining_time < :hi
            GROUP BY s.id ORDER BY rev DESC LIMIT 1
        """), {"lo": "2026-10-24 00:00:00", "hi": "2026-11-07 00:00:00"}).one()
    assert top["name"] == row[0]
    assert top["revenue"] == round(float(row[1]), 2)


def test_portfolio_invariants(client_with_data):
    client, _ = client_with_data
    data = client.get("/api/analysis/portfolio", params=RANGE).json()["data"]
    dishes = data["dishes"]
    assert len(dishes) == 120
    assert {d["quadrant"] for d in dishes} <= {"明星", "金牛", "问题", "瘦狗"}
    assert {d["abc"] for d in dishes} <= {"A", "B", "C"}
    # 阈值与响应数据的中位数一致
    import statistics
    assert data["thresholds"]["qty_median"] == statistics.median(d["quantity"] for d in dishes)
    # 象限判定与阈值一致（抽查全部）
    qm, mm = data["thresholds"]["qty_median"], data["thresholds"]["margin_median"]
    for d in dishes:
        hq, hm = d["quantity"] >= qm, d["margin_rate"] >= mm
        expect = "明星" if hq and hm else "金牛" if hm else "问题" if hq else "瘦狗"
        assert d["quadrant"] == expect


def test_waste_totals_and_alerts(client_with_data):
    client, engine = client_with_data
    data = client.get("/api/analysis/waste", params=RANGE).json()["data"]
    prepared = sql_scalar(engine, "SELECT SUM(prepared_qty) FROM waste_record WHERE date BETWEEN :s AND :e",
                          s=RANGE["start"], e=RANGE["end"])
    assert data["totals"]["prepared"] == prepared
    for alert in data["alerts"]:
        assert alert["waste_rate"] > 0.15
        assert alert["prepared"] >= 50


def test_reviews_summary_matches_raw_sql(client_with_data):
    client, engine = client_with_data
    data = client.get("/api/analysis/reviews", params=RANGE).json()["data"]
    count = sql_scalar(engine, "SELECT COUNT(*) FROM review WHERE created_at >= :lo AND created_at < :hi",
                       lo="2026-10-24 00:00:00", hi="2026-11-07 00:00:00")
    assert data["summary"]["count"] == count
    assert sum(int(v) for v in data["summary"]["rating_dist"].values()) == count


def test_dishes_list_filter_and_detail(client_with_data):
    client, _ = client_with_data
    data = client.get("/api/dishes", params={**RANGE, "keyword": "宫保", "page_size": 10}).json()["data"]
    assert data["total"] == 2  # 宫保鸡丁、宫保虾球套餐
    dish_id = data["items"][0]["dish_id"]
    detail = client.get(f"/api/dishes/{dish_id}/analysis", params=RANGE).json()
    assert detail["code"] == 0
    assert len(detail["data"]["trend"]) == 14
    missing = client.get("/api/dishes/99999/analysis", params=RANGE)
    assert missing.status_code == 404
    assert missing.json()["code"] == 1002
    assert missing.json()["msg"] == "菜品不存在"


def test_invalid_range_msg(client_with_data):
    client, _ = client_with_data
    resp = client.get("/api/dashboard/overview",
                      params={"start": "2026-11-06", "end": "2026-10-24"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001
    assert resp.json()["msg"] == "开始日期不能晚于结束日期"


def test_analysis_requires_token(client):
    resp = client.get("/api/analysis/portfolio")
    assert resp.status_code == 401
    assert resp.json()["code"] == 2001