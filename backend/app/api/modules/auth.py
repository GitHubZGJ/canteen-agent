"""认证接口：登录与当前用户。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.response import ok
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    return ok(auth_service.login(db, body.username, body.password))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok({"id": user.id, "username": user.username, "role": user.role})