"""默认用户播种：仅在 user 表为空时创建，幂等。

演示账号见 README；生产部署后应立即改密。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User

DEFAULT_USERS = [
    ("admin", "Admin@123", "admin"),
    ("manager", "Manager@123", "manager"),
    ("viewer", "Viewer@123", "viewer"),
]


def seed_default_users(db: Session) -> int:
    if db.scalar(select(User).limit(1)) is not None:
        return 0
    for username, password, role in DEFAULT_USERS:
        db.add(User(username=username, password_hash=hash_password(password), role=role))
    db.commit()
    return len(DEFAULT_USERS)