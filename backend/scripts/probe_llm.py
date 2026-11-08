"""LLM 接入探测：验证 OpenAI 兼容端点与模型可用性（只读小调用，不打印密钥）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import settings


def probe(model: str) -> bool:
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "只回复两个字：正常"}],
        "max_tokens": 8,
    }
    try:
        # trust_env=False：本机代理环境变量有畸形值，国内端点直连即可
        with httpx.Client(trust_env=False, timeout=30) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
    except httpx.HTTPError as exc:
        print(f"[FAIL] {model} 网络错误：{exc}")
        return False
    if resp.status_code != 200:
        print(f"[FAIL] {model} HTTP {resp.status_code}：{resp.text[:200]}")
        return False
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    print(f"[PASS] {model} 实际返回模型={data.get('model')} 内容={content!r}")
    return True


if __name__ == "__main__":
    if not settings.llm_enabled:
        print("未配置 LLM，跳过探测（规则模式可用）")
        sys.exit(0)
    candidates = [settings.llm_model]
    if "glm-4.5-flash" not in candidates:
        candidates.append("glm-4.5-flash")
    results = {m: probe(m) for m in candidates}
    sys.exit(0 if any(results.values()) else 1)