"""M4 验收验证：规则模式对话审计、工单闭环全流程、周报、权限、真实 LLM 冒烟。

退出码：0 全部通过；1 存在失败项。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"（{detail}）" if detail else ""))


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def main() -> None:
    with TestClient(app) as client:
        admin = client.post("/api/auth/login",
                            json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
        client.headers["Authorization"] = f"Bearer {admin}"

        # ---- 规则模式对话：审计与回答 ----
        sid = client.post("/api/agent/sessions", json={"mode": "rule"}).json()["data"]["id"]
        events = parse_sse(client.post(f"/api/agent/sessions/{sid}/messages",
                                       json={"content": "看看最近的经营指标"}).text)
        types = [e["type"] for e in events]
        check("规则对话产生工具调用与答复",
              "tool_call" in types and "message" in types and "done" in types)
        message = next(e for e in events if e["type"] == "message")
        check("答复数字来自工具结果", "营收" in message["content"] and "¥" in message["content"])
        history = client.get(f"/api/agent/sessions/{sid}/messages").json()["data"]
        assistant = [m for m in history["messages"] if m["role"] == "assistant"][-1]
        check("工具调用已审计（含耗时与状态）",
              assistant["tool_calls"] and assistant["tool_calls"][0]["status"] == "ok"
              and assistant["tool_calls"][0]["latency_ms"] >= 0)

        # ---- 智能体创建建议 → 人工审批 → 执行 → 评估 → 闭环 ----
        events = parse_sse(client.post(f"/api/agent/sessions/{sid}/messages",
                                       json={"content": "帮我创建建议"}).text)
        result = next(e for e in events if e["type"] == "tool_result"
                      and e["tool"] == "create_suggestion")
        check("智能体仅创建草稿建议", result["status"] == "ok" and "suggestion_id" in result["summary"])
        suggestion_id = json.loads(result["summary"])["suggestion_id"]

        detail = client.post(f"/api/suggestions/{suggestion_id}/review",
                             json={"approve": True, "note": "采纳"}).json()["data"]
        check("人工审批后生效", detail["status"] == "approved")
        detail = client.post(f"/api/suggestions/{suggestion_id}/execute",
                             json={"note": "已执行"}).json()["data"]
        check("执行登记", detail["status"] == "in_progress" and detail["executed_at"])
        detail = client.post(f"/api/suggestions/{suggestion_id}/evaluate",
                             json={"note": "复盘"}).json()["data"]
        check("评估闭环且效果落库",
              detail["status"] == "closed" and detail["effect_count"] == 6,
              f"effect_count={detail['effect_count']}")
        check("状态迁移事件完整", len([e for e in detail["events"]]) == 5,
              f"{len(detail['events'])} 条事件")

        # ---- 周报 ----
        report = client.post("/api/reports/weekly", json={"days": 7}).json()["data"]
        check("周报生成且含核心指标",
              "核心指标" in report["content_md"] and "营收" in report["content_md"]
              and "工单进展" in report["content_md"])
        check("周报可检索", client.get(f"/api/reports/{report['id']}").json()["data"]["id"] == report["id"])

        # ---- 权限 ----
        viewer = client.post("/api/auth/login",
                             json={"username": "viewer", "password": "Viewer@123"}).json()["data"]["token"]
        denied = client.post("/api/suggestions", json={"type": "other", "title": "越权测试"},
                             headers={"Authorization": f"Bearer {viewer}"})
        check("viewer 无法创建工单", denied.status_code == 403 and denied.json()["msg"] == "权限不足")
        foreign = client.get(f"/api/agent/sessions/{sid}/messages",
                             headers={"Authorization": f"Bearer {viewer}"})
        check("会话归属隔离", foreign.status_code == 403 and foreign.json()["msg"] == "无权访问该会话")

        # ---- 真实 LLM（有 Key 时） ----
        if settings.llm_enabled:
            auto_sid = client.post("/api/agent/sessions",
                                   json={"mode": "auto", "title": "LLM 验收"}).json()["data"]["id"]
            llm_events = parse_sse(client.post(f"/api/agent/sessions/{auto_sid}/messages",
                                               json={"content": "看看最近 30 天的经营指标"}).text)
            modes = [e["mode"] for e in llm_events if e["type"] == "mode"]
            check("大模型模式完成工具调用", modes == ["llm"]
                  and any(e["type"] == "tool_call" for e in llm_events)
                  and any(e["type"] == "message" for e in llm_events))
        else:
            print("[SKIP] 未配置大模型，仅验证规则模式")

    failed = RESULTS.count(False)
    print(f"\n合计 {len(RESULTS)} 项，失败 {failed} 项")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()