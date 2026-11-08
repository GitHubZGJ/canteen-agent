"""建议工单接口：查询、创建、审批、执行、效果评估。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.response import ok
from app.models import User
from app.schemas.suggestions import NoteIn, ReviewIn, SuggestionCreate
from app.services import suggestion_service

router = APIRouter(prefix="/api/suggestions", tags=["决策闭环"],
                   dependencies=[Depends(get_current_user)])


@router.get("")
def list_suggestions(status: str | None = None,
                     page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                     db: Session = Depends(get_db)):
    return ok(suggestion_service.list_suggestions(db, status, page, page_size))


@router.post("")
def create_suggestion(body: SuggestionCreate, db: Session = Depends(get_db),
                      user: User = Depends(require_role("admin", "manager"))):
    return ok(suggestion_service.create_suggestion(
        db, user, body.type, body.title, body.content, body.run_id))


@router.get("/{suggestion_id}")
def detail(suggestion_id: int, db: Session = Depends(get_db)):
    return ok(suggestion_service.detail(db, suggestion_id))


@router.post("/{suggestion_id}/review")
def review(suggestion_id: int, body: ReviewIn, db: Session = Depends(get_db),
           user: User = Depends(require_role("admin", "manager"))):
    return ok(suggestion_service.review(db, suggestion_id, user, body.approve, body.note))


@router.post("/{suggestion_id}/execute")
def execute(suggestion_id: int, body: NoteIn, db: Session = Depends(get_db),
            user: User = Depends(require_role("admin", "manager"))):
    return ok(suggestion_service.execute(db, suggestion_id, user, body.note))


@router.post("/{suggestion_id}/evaluate")
def evaluate(suggestion_id: int, body: NoteIn, db: Session = Depends(get_db),
             user: User = Depends(require_role("admin", "manager"))):
    return ok(suggestion_service.evaluate(db, suggestion_id, user, body.note))