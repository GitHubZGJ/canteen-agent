"""工具注册表：智能体触达数据的唯一入口，负责 schema 校验与审计元信息。"""
import json
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.core.exceptions import ERR_PARAM, BizException


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    func: Callable
    write: bool = False


TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, description: str, args_model: type[BaseModel], write: bool = False):
    def decorator(func: Callable) -> Callable:
        TOOLS[name] = ToolSpec(name=name, description=description,
                               args_model=args_model, func=func, write=write)
        return func

    return decorator


def openai_tools() -> list[dict]:
    return [
        {"type": "function",
         "function": {"name": spec.name, "description": spec.description,
                      "parameters": spec.args_model.model_json_schema()}}
        for spec in TOOLS.values()
    ]


def execute_tool(db, user, name: str, args: dict | None) -> dict:
    spec = TOOLS.get(name)
    if spec is None:
        raise BizException(ERR_PARAM, f"未知工具：{name}")
    try:
        parsed = spec.args_model.model_validate(args or {})
    except ValidationError as exc:
        first = exc.errors()[0]
        raise BizException(ERR_PARAM, f"工具参数校验失败：{first.get('loc')} {first.get('msg')}")
    return spec.func(db, user, **parsed.model_dump())


def summarize_result(result: dict, limit: int = 600) -> str:
    text = json.dumps(result, ensure_ascii=False)
    return text[:limit]