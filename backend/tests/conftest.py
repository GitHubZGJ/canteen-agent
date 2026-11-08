"""测试夹具：临时 SQLite + 依赖覆盖，不触碰真实库（不启用 lifespan）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User


def _build_client(tmp_path, with_data: bool, days: int = 14):
    engine = create_engine(
        f"sqlite:///{tmp_path.as_posix()}/test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        db.add_all([
            User(username="admin", password_hash=hash_password("Admin@123"), role="admin"),
            User(username="viewer", password_hash=hash_password("Viewer@123"), role="viewer"),
        ])
        db.commit()
        if with_data:
            from datetime import date

            from scripts.generate_data import generate
            generate(db, days=days, seed=42, end_date=date(2026, 11, 6))

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.session_factory = session_factory
    # 不用 with：避免触发 lifespan 对真实库执行迁移与播种
    client = TestClient(app)
    return client, engine


@pytest.fixture()
def client(tmp_path):
    client, engine = _build_client(tmp_path, with_data=False)
    yield client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def client_with_data(tmp_path):
    """带 14 天模拟数据（2026-10-24 ～ 2026-11-06）与登录 token 的客户端。"""
    client, engine = _build_client(tmp_path, with_data=True)
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def client_with_long_data(tmp_path):
    """带 60 天模拟数据，满足预测回测跨度要求。"""
    client, engine = _build_client(tmp_path, with_data=True, days=60)
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "Admin@123"}).json()["data"]["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()