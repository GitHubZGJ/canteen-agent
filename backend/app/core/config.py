"""环境配置：只读项目根目录 .env，缺省值保证无 Key 可跑。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> 上溯 3 级到项目根
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'canteen.db').as_posix()}"
    jwt_secret: str = ""
    jwt_expire_hours: int = 24
    jwt_algorithm: str = "HS256"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    agent_max_steps: int = 8

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)


settings = Settings()