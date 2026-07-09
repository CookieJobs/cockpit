"""拾光配置管理。

通过 pydantic-settings 从 .env / 环境变量加载配置。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """拾光全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用 =====
    shiguang_env: Literal["development", "production", "test"] = Field(
        default="development", alias="SHIGUANG_ENV"
    )
    shiguang_data_dir: Path = Field(
        default=Path.home() / ".shiguang", alias="SHIGUANG_DATA_DIR"
    )
    shiguang_port: int = Field(default=7842, alias="SHIGUANG_PORT")
    shiguang_host: str = Field(default="127.0.0.1", alias="SHIGUANG_HOST")

    # ===== LLM 后端 =====
    shiguang_llm_backend: Literal["anthropic", "ollama", "openai"] = Field(
        default="anthropic", alias="SHIGUANG_LLM_BACKEND"
    )
    shiguang_llm_model: str = Field(
        default="claude-sonnet-4-5", alias="SHIGUANG_LLM_MODEL"
    )

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL"
    )

    # Ollama
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="qwen2.5:3b", alias="OLLAMA_MODEL")

    # OpenAI 兼容
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="", alias="OPENAI_MODEL")

    # ===== 数据库 =====
    database_url: str = Field(default="", alias="DATABASE_URL")

    # ===== 安全 =====
    shiguang_encryption_key: str = Field(
        default="", alias="SHIGUANG_ENCRYPTION_KEY"
    )

    def get_database_url(self) -> str:
        """获取异步数据库 URL（默认 SQLite via aiosqlite）。"""
        if self.database_url:
            return self.database_url
        # 确保数据目录存在
        self.shiguang_data_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.shiguang_data_dir / "shiguang.db"
        return f"sqlite+aiosqlite:///{db_path}"


settings = Settings()
