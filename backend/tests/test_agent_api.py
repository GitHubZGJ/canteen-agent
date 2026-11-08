"""智能体接口测试：规则模式、写权限、大模型循环（FakeProvider）、失败降级、SSE。"""
import json

from app.core.config import settings


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def new_session(client, mode="rule", token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return client.post("/api/agent/sessions", json={"mode": mode}, headers=headers).json()["data"]


def chat(client, session_id, content, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else None
    return client.post(f"/api/agent/sessions/{session_id}/messages",
                       json={"content": content}, headers=headers)


class FakeProvider:
    """脚本化大模型：第一步调用 query_metrics，第二步给出最终答复。"""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {"content": "", "tool_calls": [
                {"id": "call-1", "name": "query_metrics", "arguments": "{}"}]}
        return {"content": "查询完成：经营指标已在上方工具结果中。", "tool_calls": []}


class FailingProvider:
    def chat(self, messages, tools):
        raise RuntimeError("upstream 502")


def test_rule_chat_with_audit(client_with_data):
    client, _ = client_with_data
    sid = new_session(client)["id"]
    resp = chat(client, sid, "看看最近的经营指标")
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert "tool_call" in types and "tool_result" in types
    assert "message" in types and "done" in types
    message = next(e for e in events if e["type"] == "message")
    assert "营收" in message["content"]

    history = client.get(f"/api/agent/sessions/{sid}/messages").json()["data"]
    assistant = [m for m in history["messages"] if m["role"] == "assistant"][-1]
    assert assistant["tool_calls"][0]["tool"] == "query_metrics"
    assert assistant["tool_calls"][0]["status"] == "ok"
    assert history["messages"][0]["role"] == "user"


def test_rule_chat_creates_suggestion(client_with_data):
    client, _ = client_with_data
    sid = new_session(client)["id"]
    resp = chat(client, sid, "帮我创建建议")
    events = parse_sse(resp.text)
    result = next(e for e in events if e["type"] == "tool_result"
                  and e["tool"] == "create_suggestion")
    assert result["status"] == "ok"
    suggestions = client.get("/api/suggestions").json()["data"]
    assert suggestions["total"] == 1
    assert suggestions["items"][0]["status"] == "draft"


def test_viewer_write_tool_blocked(client_with_data):
    client, _ = client_with_data
    token = client.post("/api/auth/login",
                        json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
    sid = new_session(client, token=token)["id"]
    resp = chat(client, sid, "创建建议", token=token)
    events = parse_sse(resp.text)
    result = next(e for e in events if e["type"] == "tool_result"
                  and e["tool"] == "create_suggestion")
    assert result["status"] == "error"
    assert "无写操作权限" in result["summary"]
    assert client.get("/api/suggestions").json()["data"]["total"] == 0


def test_llm_loop_with_fake_provider(client_with_data, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "http://fake")
    monkeypatch.setattr(settings, "llm_model", "fake-model")
    monkeypatch.setattr("app.agent.engine.build_provider", lambda: FakeProvider())
    client, _ = client_with_data
    sid = new_session(client, mode="auto")["id"]
    resp = chat(client, sid, "现在经营怎么样")
    events = parse_sse(resp.text)
    assert next(e for e in events if e["type"] == "mode")["mode"] == "llm"
    assert any(e["type"] == "tool_call" and e["tool"] == "query_metrics" for e in events)
    done = next(e for e in events if e["type"] == "done")
    assert done["mode"] == "llm"
    message = next(e for e in events if e["type"] == "message")
    assert "查询完成" in message["content"]


def test_llm_failure_falls_back_to_rules(client_with_data, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "http://fake")
    monkeypatch.setattr(settings, "llm_model", "fake-model")
    monkeypatch.setattr("app.agent.engine.build_provider", lambda: FailingProvider())
    client, _ = client_with_data
    sid = new_session(client, mode="auto")["id"]
    resp = chat(client, sid, "看看经营指标")
    events = parse_sse(resp.text)
    assert any(e["type"] == "fallback" for e in events)
    message = next(e for e in events if e["type"] == "message")
    assert "营收" in message["content"]


def test_session_ownership(client_with_data):
    client, _ = client_with_data
    sid = new_session(client)["id"]
    token = client.post("/api/auth/login",
                        json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
    resp = client.get(f"/api/agent/sessions/{sid}/messages",
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["msg"] == "无权访问该会话"


def test_reports_weekly(client_with_data):
    client, _ = client_with_data
    resp = client.post("/api/reports/weekly", json={"days": 7})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "核心指标" in data["content_md"] and "营收" in data["content_md"]
    listing = client.get("/api/reports").json()["data"]
    assert listing[0]["id"] == data["id"]
    detail = client.get(f"/api/reports/{data['id']}").json()["data"]
    assert detail["period"] == data["period"]
    token = client.post("/api/auth/login",
                        json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
    forbidden = client.post("/api/reports/weekly", json={"days": 7},
                            headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403