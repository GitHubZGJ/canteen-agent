"""认证领域逻辑。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ERR_BAD_CREDENTIALS, BizException
from app.core.security import create_token, verify_password
from app.models.user import User


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        raise BizException(ERR_BAD_CREDENTIALS, "用户名或密码错误")
    return user


def login(db: Session, username: str, password: str) -> dict:
    user = authenticate(db, username, password)
    return {
        "token": create_token(user.id, user.role),
        "user": {"id": user.id, "username": user.username, "role": user.role},
    }