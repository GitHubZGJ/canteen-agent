"""提交前密钥自查：高熵密钥按值扫描 + 代码字面量扫描。

- 按值扫描：.env 里的 JWT_SECRET、LLM_API_KEY 真实值不得出现在仓库任何其他文件。
- 字面量扫描：代码中形如 key/secret/token = "长随机串" 的赋值视为可疑候选。
退出码：0 干净；1 发现泄漏或候选。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".venv", ".git", "node_modules", ".pip-cache", ".npm-cache", ".run",
             "data", "__pycache__", ".pytest_cache", ".ruff_cache", "dist"}
SKIP_FILES = {".env"}
TEXT_EXT = {".py", ".md", ".txt", ".toml", ".ini", ".yml", ".yaml", ".json",
            ".js", ".ts", ".vue", ".html", ".css", ".example", ".mako", ".cfg"}
LITERAL_RE = re.compile(
    r"""(?i)(api_key|apikey|secret|token|password)\s*[:=]\s*["'][A-Za-z0-9_\-./+=]{20,}["']"""
)


def load_secrets() -> dict[str, str]:
    secrets = {}
    env = ROOT / ".env"
    if not env.exists():
        return secrets
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key in ("JWT_SECRET", "LLM_API_KEY") and len(value) >= 20 and value != "change-me":
            secrets[key] = value
    return secrets


def main() -> None:
    secrets = load_secrets()
    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() not in TEXT_EXT and path.name != ".env.example":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(ROOT)
        for name, value in secrets.items():
            if value in text:
                findings.append(f"[泄漏] {rel} 包含 .env 中的 {name} 真实值")
        if path.suffix == ".py":
            for m in LITERAL_RE.finditer(text):
                findings.append(f"[候选] {rel} 疑似硬编码密钥：{m.group(1)} = <长字符串>")
    if findings:
        print("\n".join(findings))
        print(f"\n共 {len(findings)} 项，需人工确认")
        sys.exit(1)
    print(f"[PASS] 密钥自查干净（按值扫描 {len(secrets)} 个密钥 + 字面量扫描）")


if __name__ == "__main__":
    main()