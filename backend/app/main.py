"""应用入口：组装异常处理、路由自动发现、启动迁移与播种。"""
from contextlib import asynccontextmanager

from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alembic import command
from app.api import include_routers
from app.core.config import BACKEND_DIR, PROJECT_ROOT
from app.core.database import SessionLocal
from app.core.exceptions import register_exception_handlers
from app.services.seed import seed_default_users


def run_migrations() -> None:
    """启动时执行 alembic upgrade head，保证克隆即跑。"""
    (PROJECT_ROOT / "data").mkdir(exist_ok=True)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_migrations()
    with SessionLocal() as db:
        seed_default_users(db)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="校园食堂智能体", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    include_routers(app)
    app.state.session_factory = SessionLocal  # 流式接口在响应期间自建会话
    return app


app = create_app()