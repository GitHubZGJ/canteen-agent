"""预测与优化接口集成测试：机制、权限、确定性、约束。"""


def test_forecast_single_dish(client_with_long_data):
    client, _ = client_with_long_data
    resp = client.post("/api/forecast/runs", json={"dish_id": 1, "horizon": 14})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["run_id"] >= 1
    assert data["metrics"]["chosen"]["mae"] is not None
    assert data["metrics"]["seasonal_naive"]["mae"] is not None
    run_id = data["run_id"]
    detail = client.get(f"/api/forecast/runs/{run_id}").json()["data"]
    assert len(detail["series"]) == 3                 # 三个时段
    assert all(len(s["points"]) == 14 for s in detail["series"])
    assert all("actual" in p and "lower" in p for s in detail["series"] for p in s["points"])
    assert client.get("/api/forecast/runs").json()["data"][0]["id"] == run_id


def test_forecast_insufficient_span(client_with_data):
    client, _ = client_with_data
    resp = client.post("/api/forecast/runs", json={"horizon": 14})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001
    assert "数据跨度不足" in resp.json()["msg"]


def test_forecast_requires_manager(client_with_long_data):
    client, _ = client_with_long_data
    token = client.post("/api/auth/login",
                        json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
    resp = client.post("/api/forecast/runs", json={"dish_id": 1},
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["code"] == 2002
    assert resp.json()["msg"] == "权限不足"


def test_forecast_missing_dish(client_with_long_data):
    client, _ = client_with_long_data
    resp = client.post("/api/forecast/runs", json={"dish_id": 99999})
    assert resp.status_code == 404
    assert resp.json()["msg"] == "菜品不存在"


def test_optimization_run_and_determinism(client_with_data):
    client, _ = client_with_data
    a = client.post("/api/optimization/runs", json={}).json()["data"]
    assert sum(a["counts"].values()) == 120
    assert len(a["dishes"]) == 120
    assert {d["action"] for d in a["dishes"]} <= {"推广", "保留", "汰换"}
    b = client.post("/api/optimization/runs", json={}).json()["data"]
    assert a["dishes"] == b["dishes"]                 # 固定输入完全可复现
    detail = client.get(f"/api/optimization/runs/{a['run_id']}").json()["data"]
    assert detail["counts"] == a["counts"]


def test_optimization_protected_not_removed(client_with_data):
    client, _ = client_with_data
    first = client.post("/api/optimization/runs", json={}).json()["data"]
    lowest = min(first["dishes"], key=lambda d: d["score"])["dish_id"]
    second = client.post("/api/optimization/runs", json={"protected": [lowest]}).json()["data"]
    target = next(d for d in second["dishes"] if d["dish_id"] == lowest)
    assert target["action"] != "汰换"


def test_optimization_invalid_period(client_with_data):
    client, _ = client_with_data
    resp = client.post("/api/optimization/runs", json={"period_days": 3})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001
    assert "参数校验失败" in resp.json()["msg"]