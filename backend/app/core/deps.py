"""鉴权依赖：当前用户与角色校验（对应既定 @RequireRole 写法）。"""
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ERR_FORBIDDEN, ERR_UNAUTHORIZED, BizException
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise BizException(ERR_UNAUTHORIZED, "未登录或缺少 token", http_status=401)
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise BizException(ERR_UNAUTHORIZED, "token 无效或已过期", http_status=401)
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise BizException(ERR_UNAUTHORIZED, "用户不存在", http_status=401)
    return user


def require_role(*roles: str):
    """角色依赖工厂：require_role("admin", "manager")。"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise BizException(ERR_FORBIDDEN, "权限不足", http_status=403)
        return user

    return checker