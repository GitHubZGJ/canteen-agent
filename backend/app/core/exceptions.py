"""业务异常与全局异常处理：错误码分段见 docs/architecture.md。"""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class BizException(Exception):
    """业务异常：code 为业务错误码，http_status 为 HTTP 状态码。"""

    def __init__(self, code: int, msg: str, http_status: int = 400):
        self.code = code
        self.msg = msg
        self.http_status = http_status
        super().__init__(msg)


# 常用错误码常量，避免散落魔法数字
ERR_PARAM = 1001          # 参数校验失败
ERR_UNAUTHORIZED = 2001   # 未登录或 token 无效
ERR_FORBIDDEN = 2002      # 角色权限不足
ERR_BAD_CREDENTIALS = 3001  # 用户名或密码错误
ERR_SERVER = 5000         # 系统内部错误


def _body(code: int, msg: str) -> dict:
    return {"code": code, "msg": msg, "data": None}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizException)
    async def biz_handler(_: Request, exc: BizException):
        return JSONResponse(status_code=exc.http_status, content=_body(exc.code, exc.msg))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []))
        msg = f"参数校验失败：{loc} {first.get('msg', '')}".strip()
        return JSONResponse(status_code=400, content=_body(ERR_PARAM, msg))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException):
        code = {401: ERR_UNAUTHORIZED, 403: ERR_FORBIDDEN, 404: 1002}.get(
            exc.status_code, exc.status_code
        )
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception):
        return JSONResponse(status_code=500, content=_body(ERR_SERVER, "系统内部错误"))