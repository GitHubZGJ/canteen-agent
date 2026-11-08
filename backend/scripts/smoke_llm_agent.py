"""真实大模型智能体冒烟：一次 auto 会话对话，输出事件类型与答复摘要（不打印密钥）。

用法（backend 目录）：.venv/Scripts/python.exe scripts/smoke_llm_agent.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def main() -> None:
    if not settings.llm_enabled:
        print("未配置大模型，跳过（规则模式已由测试覆盖）")
        return
    with TestClient(app) as client:
        token = client.post("/api/auth/login",
                            json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        session = client.post("/api/agent/sessions",
                              json={"mode": "auto", "title": "LLM 冒烟"}).json()["data"]
        print(f"会话 {session['id']} 模式={session['mode']}")
        resp = client.post(f"/api/agent/sessions/{session['id']}/messages",
                           json={"content": "看看最近 30 天的经营指标，用两句话总结"})
        events = []
        for block in resp.text.split("\n\n"):
            for line in block.splitlines():
                if line.startswith("data: "):
                    events.append(json.loads(line[len("data: "):]))
        print("事件序列：", [e["type"] for e in events])
        for e in events:
            if e["type"] == "tool_call":
                print(f"  工具调用：{e['tool']} 参数={json.dumps(e['args'], ensure_ascii=False)}")
            if e["type"] == "fallback":
                print(f"  降级：{e['reason']}")
        message = next((e for e in events if e["type"] == "message"), None)
        if message:
            print("答复摘要：", message["content"][:200].replace("\n", " "))
        ok = any(e["type"] == "tool_call" for e in events) and message is not None
        print("结果：", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()