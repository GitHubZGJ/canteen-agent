"""开发服务器启停：start / stop / status。

PID 取自 subprocess.Popen.pid（Windows 原生 PID），落盘 .run/backend.pid，
避免 Git Bash PID 与 Windows PID 混用杀错进程。
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from http.client import HTTPException
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
RUN_DIR = BACKEND.parent / ".run"
PID_FILE = RUN_DIR / "backend.pid"
LOG_FILE = RUN_DIR / "backend.log"
VENV_PY = BACKEND / ".venv" / "Scripts" / "python.exe"
HEALTH_URL = "http://127.0.0.1:8000/api/health"


def _healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1) as resp:
            return resp.status == 200
    except (OSError, HTTPException):
        return False


def start() -> None:
    if PID_FILE.exists() and _healthy():
        print(f"已在运行（PID {PID_FILE.read_text().strip()}）")
        return
    RUN_DIR.mkdir(exist_ok=True)
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(LOG_FILE, "ab") as log:
        proc = subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=BACKEND, stdout=log, stderr=log, creationflags=flags,
        )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    for _ in range(30):
        if _healthy():
            print(f"启动成功 PID={proc.pid}，日志 {LOG_FILE}")
            return
        time.sleep(1)
    print("启动超时，日志末尾：")
    print(LOG_FILE.read_text(encoding="utf-8", errors="replace")[-2000:])
    sys.exit(1)


def stop() -> None:
    if not PID_FILE.exists():
        print("无 PID 记录，未启动")
        return
    pid = PID_FILE.read_text(encoding="utf-8").strip()
    subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                   capture_output=True, check=False)
    PID_FILE.unlink(missing_ok=True)
    print(f"已停止 PID={pid}")


def status() -> None:
    pid = PID_FILE.read_text(encoding="utf-8").strip() if PID_FILE.exists() else "无"
    print(f"PID={pid}，健康检查={'通过' if _healthy() else '未通过'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="后端开发服务器启停")
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    {"start": start, "stop": stop, "status": status}[args.action]()