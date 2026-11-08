"""智能体审计：会话、消息、工具调用日志。"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentSession(Base):
    __tablename__ = "agent_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="新会话")
    mode: Mapped[str] = mapped_column(String(8), default="rule")  # llm / rule
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentMessage(Base):
    __tablename__ = "agent_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("agent_session.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user / assistant / tool
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ToolCallLog(Base):
    __tablename__ = "tool_call_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("agent_message.id"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(64))
    args_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16))  # ok / error
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())