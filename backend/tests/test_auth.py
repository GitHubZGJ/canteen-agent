"""认证接口测试：负向用例同时断言状态码、业务码与 msg，避免假通过。"""


def login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_ok(client):
    resp = login(client, "admin", "Admin@123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["user"]["role"] == "admin"


def test_login_wrong_password(client):
    resp = login(client, "admin", "wrong-pass")
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 3001
    assert body["msg"] == "用户名或密码错误"


def test_login_unknown_user_same_msg(client):
    resp = login(client, "nobody", "whatever")
    assert resp.status_code == 400
    assert resp.json()["code"] == 3001
    assert resp.json()["msg"] == "用户名或密码错误"


def test_login_missing_field(client):
    resp = client.post("/api/auth/login", json={"username": "admin"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 1001
    assert "参数校验失败" in body["msg"]


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == 2001
    assert body["msg"] == "未登录或缺少 token"


def test_me_bad_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 2001


def test_me_ok(client):
    token = login(client, "admin", "Admin@123").json()["data"]["token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["username"] == "admin"


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"