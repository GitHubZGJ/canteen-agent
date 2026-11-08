"""智能体接口：会话管理、历史消息与 SSE 流式对话。"""
import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.engine import AgentEngine
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.core.exceptions import ERR_FORBIDDEN, BizException
from app.core.response import ok
from app.models import AgentMessage, AgentSession, ToolCallLog, User
from app.schemas.agent import MessageIn, SessionCreate

router = APIRouter(prefix="/api/agent", tags=["智能体"],
                   dependencies=[Depends(get_current_user)])


def _own_session(db: Session, session_id: int, user: User) -> AgentSession:
    session = db.get(AgentSession, session_id)
    if session is None:
        raise BizException(1002, "会话不存在", http_status=404)
    if session.user_id != user.id:
        raise BizException(ERR_FORBIDDEN, "无权访问该会话", http_status=403)
    return session


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(AgentSession).where(AgentSession.user_id == user.id)
        .order_by(AgentSession.id.desc()).limit(30)
    ).scalars().all()
    return ok([{"id": s.id, "title": s.title, "mode": s.mode,
                "created_at": str(s.created_at)} for s in rows])


@router.post("/sessions")
def create_session(body: SessionCreate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    mode = "rule" if body.mode == "rule" else ("llm" if settings.llm_enabled else "rule")
    session = AgentSession(user_id=user.id, title=body.title, mode=mode)
    db.add(session)
    db.commit()
    return ok({"id": session.id, "title": session.title, "mode": session.mode})


@router.get("/sessions/{session_id}/messages")
def list_messages(session_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    session = _own_session(db, session_id, user)
    rows = db.execute(
        select(AgentMessage).where(AgentMessage.session_id == session.id)
        .order_by(AgentMessage.id)
    ).scalars().all()
    assistant_ids = [r.id for r in rows if r.role == "assistant"]
    logs = db.execute(
        select(ToolCallLog).where(ToolCallLog.message_id.in_(assistant_ids))
        .order_by(ToolCallLog.id)
    ).scalars().all() if assistant_ids else []
    grouped: dict[int, list] = {}
    for log in logs:
        grouped.setdefault(log.message_id, []).append({
            "tool": log.tool_name, "args": log.args_json, "status": log.status,
            "latency_ms": log.latency_ms, "summary": log.result_summary,
        })
    return ok({"mode": session.mode, "title": session.title,
               "messages": [{"id": r.id, "role": r.role, "content": r.content,
                             "created_at": str(r.created_at),
                             "tool_calls": grouped.get(r.id, [])} for r in rows]})


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: int, body: MessageIn, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = _own_session(db, session_id, user)
    history_rows = db.execute(
        select(AgentMessage).where(AgentMessage.session_id == session.id)
        .order_by(AgentMessage.id.desc()).limit(10)
    ).scalars().all()
    history = [{"role": r.role, "content": r.content}
               for r in reversed(history_rows) if r.content]
    db.add(AgentMessage(session_id=session.id, role="user", content=body.content))
    db.commit()
    user_id = user.id
    # 测试可替换 app.state.session_factory，生产默认真实库
    session_factory = getattr(request.app.state, "session_factory", SessionLocal)

    def generator() -> Iterator[str]:
        with session_factory() as stream_db:
            stream_session = stream_db.get(AgentSession, session_id)
            stream_user = stream_db.get(User, user_id)
            engine = AgentEngine(stream_db, stream_session, stream_user, history)
            try:
                for event in engine.stream(body.content):
                    yield _sse(event)
            except Exception as exc:  # noqa: BLE001 - 流内兜底，任何异常都要转成 SSE 错误事件
                yield _sse({"type": "error", "message": f"对话处理失败：{str(exc)[:200]}"})

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})