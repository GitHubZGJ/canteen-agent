"""建议工单状态机与接口测试：全流程、非法迁移（连 msg 断言）、权限、效果落库。"""


def create(client, title="测试建议"):
    return client.post("/api/suggestions", json={
        "type": "menu_change", "title": title, "content": {"dish_id": 1, "action": "汰换"},
    }).json()["data"]


def test_full_closed_loop(client_with_data):
    client, _ = client_with_data
    suggestion = create(client)
    assert suggestion["status"] == "draft"
    sid = suggestion["id"]

    approved = client.post(f"/api/suggestions/{sid}/review",
                           json={"approve": True, "note": "同意"}).json()["data"]
    assert approved["status"] == "approved"
    assert approved["reviewed_by_name"] == "admin"

    executed = client.post(f"/api/suggestions/{sid}/execute",
                           json={"note": "已调整菜单"}).json()["data"]
    assert executed["status"] == "in_progress"
    assert executed["executed_at"]

    evaluated = client.post(f"/api/suggestions/{sid}/evaluate",
                            json={"note": "观察两周"}).json()["data"]
    assert evaluated["status"] == "closed"
    assert evaluated["effect_count"] >= 4          # 满意度在空窗口可能缺省
    assert len(evaluated["effects"]) == evaluated["effect_count"]
    assert {e["metric"] for e in evaluated["effects"]} >= {"revenue", "orders", "waste_rate"}
    transitions = [(e["from"], e["to"]) for e in evaluated["events"]]
    assert ("in_progress", "evaluating") in transitions
    assert ("evaluating", "closed") in transitions


def test_reject_path(client_with_data):
    client, _ = client_with_data
    sid = create(client, "驳回测试")["id"]
    rejected = client.post(f"/api/suggestions/{sid}/review",
                           json={"approve": False, "note": "收益不足"}).json()["data"]
    assert rejected["status"] == "rejected"
    resp = client.post(f"/api/suggestions/{sid}/execute", json={"note": ""})
    assert resp.status_code == 400
    assert "状态不允许" in resp.json()["msg"]


def test_illegal_transition_msg(client_with_data):
    client, _ = client_with_data
    sid = create(client)["id"]
    resp = client.post(f"/api/suggestions/{sid}/execute", json={"note": ""})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001
    assert resp.json()["msg"] == "状态不允许：当前待审批，无法执行"
    client.post(f"/api/suggestions/{sid}/review", json={"approve": True})
    again = client.post(f"/api/suggestions/{sid}/review", json={"approve": True})
    assert again.status_code == 400
    assert "无法采纳" in again.json()["msg"]


def test_viewer_forbidden_write_but_can_read(client_with_data):
    client, _ = client_with_data
    token = client.post("/api/auth/login",
                        json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
    resp = client.post("/api/suggestions", json={"type": "other", "title": "越权测试"},
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["msg"] == "权限不足"
    listing = client.get("/api/suggestions", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200


def test_missing_suggestion(client_with_data):
    client, _ = client_with_data
    resp = client.get("/api/suggestions/99999")
    assert resp.status_code == 404
    assert resp.json()["msg"] == "建议工单不存在"


def test_list_filter_by_status(client_with_data):
    client, _ = client_with_data
    create(client, "建议 A")
    sid = create(client, "建议 B")["id"]
    client.post(f"/api/suggestions/{sid}/review", json={"approve": True})
    approved = client.get("/api/suggestions", params={"status": "approved"}).json()["data"]
    assert approved["total"] == 1
    assert approved["items"][0]["title"] == "建议 B"