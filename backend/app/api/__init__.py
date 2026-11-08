"""路由自动发现：扫描 app.api.modules 下所有模块的 router 并注册。

新增业务模块只需在 modules/ 下新建文件并暴露 router，零改动接线。
"""
import importlib
import pkgutil

from fastapi import APIRouter, FastAPI

from app.api import modules


def include_routers(app: FastAPI) -> None:
    for mod_info in pkgutil.iter_modules(modules.__path__):
        module = importlib.import_module(f"app.api.modules.{mod_info.name}")
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            app.include_router(router)