"""数据管理接口测试：生成守卫、三类 CSV 导入、错误行报告、权限。"""
from sqlalchemy import text


def as_admin(client):
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def upload(client, kind, content, filename="data.csv"):
    return client.post("/api/data/import", data={"kind": kind},
                       files={"file": (filename, content.encode("utf-8"), "text/csv")})


def test_generate_on_empty_db(client):
    as_admin(client)
    resp = client.post("/api/data/generate",
                       json={"days": 30, "seed": 42, "end_date": "2026-11-06"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["canteen"] == 2 and data["stall"] == 8 and data["dish"] == 120
    assert data["orders"] > 0


def test_generate_guard_and_reset(client_with_data):
    client, _ = client_with_data
    resp = client.post("/api/data/generate", json={"days": 30, "end_date": "2026-11-06"})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001
    assert resp.json()["msg"] == "已存在经营数据；如需重建请勾选重置"
    rebuilt = client.post("/api/data/generate",
                          json={"days": 30, "seed": 7, "end_date": "2026-11-06", "reset": True})
    assert rebuilt.status_code == 200
    assert rebuilt.json()["data"]["orders"] > 0


def test_import_dishes_with_error_rows(client_with_data):
    client, _ = client_with_data
    content = (
        "stall_name,name,category,price,cost,tags,calories\n"
        "川湘风味,测试新菜,热菜,12.5,6.0,辣|招牌,520\n"
        "川湘风味,坏价格菜,热菜,-3,1.0,辣\n"
    )
    resp = upload(client, "dishes", content)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["imported"] == 1 and data["error_count"] == 1
    assert data["errors"][0]["row"] == 3
    assert "价格或成本不合法" in data["errors"][0]["msg"]
    found = client.get("/api/dishes", params={"keyword": "测试新菜"}).json()["data"]
    assert found["total"] == 1


def test_import_orders_with_duplicate(client_with_data):
    client, engine = client_with_data
    content = (
        "order_no,stall_name,dish_name,quantity,dining_time,channel,people_count\n"
        "IMP-TEST-1,川湘风味,宫保鸡丁,2,2026-11-01 12:10:00,dine_in,1\n"
        "IMP-TEST-1,川湘风味,宫保鸡丁,1,2026-11-01 12:20:00,dine_in,1\n"
    )
    resp = upload(client, "orders", content)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["imported"] == 1 and data["error_count"] == 1
    assert "订单号重复" in data["errors"][0]["msg"]
    with engine.connect() as conn:
        count = conn.execute(text(
            "SELECT COUNT(*) FROM orders WHERE order_no='IMP-TEST-1'")).scalar()
        item = conn.execute(text(
            "SELECT oi.quantity FROM order_item oi JOIN orders o ON oi.order_id=o.id "
            "WHERE o.order_no='IMP-TEST-1'")).scalar()
    assert count == 1 and item == 2


def test_import_reviews_derives_sentiment(client_with_data):
    client, engine = client_with_data
    content = (
        "stall_name,dish_name,rating,content,created_at\n"
        "轻食沙拉,鸡胸肉沙拉,2,分量偏少,2026-11-01 12:30:00\n"
    )
    resp = upload(client, "reviews", content)
    assert resp.status_code == 200
    assert resp.json()["data"]["imported"] == 1
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT r.sentiment FROM review r JOIN dish d ON r.dish_id=d.id "
            "WHERE d.name='鸡胸肉沙拉' AND r.content='分量偏少'")).scalar()
    assert row == "neg"


def test_missing_required_header(client_with_data):
    client, _ = client_with_data
    resp = upload(client, "dishes", "stall_name,name,cost\n川湘风味,菜,1\n")
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001
    assert "缺少必需列" in resp.json()["msg"]
    assert "price" in resp.json()["msg"]


def test_import_forbidden_for_viewer(client_with_data):
    client, _ = client_with_data
    token = client.post("/api/auth/login",
                        json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
    resp = client.post("/api/data/import", data={"kind": "dishes"},
                       files={"file": ("d.csv", b"stall_name\n", "text/csv")},
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["msg"] == "权限不足"


def test_template_download_and_bad_kind(client):
    as_admin(client)
    ok_resp = client.get("/api/data/templates/dishes")
    assert ok_resp.status_code == 200
    assert ok_resp.text.startswith("stall_name,name,category,price,cost")
    bad = client.get("/api/data/templates/foo")
    assert bad.status_code == 400
    assert bad.json()["msg"] == "未知模板类型：foo"