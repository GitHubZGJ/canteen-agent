"""Alembic 环境：URL 与元数据均来自应用配置，SQLite 启用 batch 模式。"""
import sys
from pathlib import Path

# 保证任意工作目录下都能导入 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context

from app import models  # noqa: F401  导入全部模型注册 metadata
from app.core.config import settings
from app.core.database import Base, engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()