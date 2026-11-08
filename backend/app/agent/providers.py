"""大模型适配层：OpenAI 兼容函数调用；无 Key 返回 None（走规则模式）。"""
import httpx

from app.core.config import settings


class OpenAICompatProvider:
    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        # trust_env=False：规避本机畸形代理变量，国内端点直连
        with httpx.Client(trust_env=False, timeout=60) as client:
            resp = client.post(
                url, json=payload,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
        if resp.status_code != 200:
            raise RuntimeError(f"大模型 HTTP {resp.status_code}：{resp.text[:200]}")
        message = resp.json()["choices"][0]["message"]
        tool_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            tool_calls.append({"id": tc.get("id", ""), "name": fn.get("name", ""),
                               "arguments": fn.get("arguments") or "{}"})
        return {"content": message.get("content") or "", "tool_calls": tool_calls}


def build_provider():
    return OpenAICompatProvider() if settings.llm_enabled else None