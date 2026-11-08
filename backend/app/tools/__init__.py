"""业务工具导入即注册。"""
from app.tools import business_tools  # noqa: F401
from app.tools.registry import TOOLS, execute_tool, openai_tools, summarize_result

__all__ = ["TOOLS", "execute_tool", "openai_tools", "summarize_result"]