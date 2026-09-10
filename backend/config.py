"""AERA runtime configuration. Motor data always comes from the Motor + HMI backend."""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    motor_api_url: str = Field(default="http://127.0.0.1:8000", alias="MOTOR_API_URL")
    motor_ws_url: str = Field(default="ws://127.0.0.1:8000/ws/runtime", alias="MOTOR_WS_URL")
    motor_code: str = Field(default="MOTOR-01", alias="MOTOR_CODE")
    host: str = Field(default="127.0.0.1", alias="AERA_HOST")
    port: int = Field(default=8001, alias="AERA_PORT")
    cors_origins: str = Field(
        default="http://localhost:3001,http://127.0.0.1:3001",
        alias="AERA_CORS_ORIGINS",
    )
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    @property
    def cors_origin_list(self) -> List[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def has_llm(self) -> bool:
        return bool(self.openai_api_key.strip())


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
