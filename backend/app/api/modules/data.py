"""数据管理接口：模拟数据生成、CSV 模板下载与导入（经理及以上可写）。"""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.response import ok
from app.services import data_service

router = APIRouter(prefix="/api/data", tags=["数据管理"],
                   dependencies=[Depends(get_current_user)])


class GenerateIn(BaseModel):
    days: int = Field(180, ge=30, le=365)
    seed: int = Field(42, ge=0, le=999999)
    end_date: date | None = None
    reset: bool = False


@router.get("/templates/{kind}")
def download_template(kind: str):
    content = data_service.template_csv(kind)
    return PlainTextResponse(content, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition":
                                      f'attachment; filename="{kind}-template.csv"'})


@router.post("/generate")
def generate(body: GenerateIn, db: Session = Depends(get_db),
             _=Depends(require_role("admin", "manager"))):
    return ok(data_service.generate_simulated(db, body.days, body.seed, body.end_date, body.reset))


@router.post("/import")
async def import_csv(kind: str = Form(...), file: UploadFile = File(...),
                     db: Session = Depends(get_db),
                     _=Depends(require_role("admin", "manager"))):
    raw = await file.read()
    return ok(data_service.import_csv(db, kind, raw))