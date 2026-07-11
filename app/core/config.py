"""Cockpit 配置管理。

通过 pydantic-settings 从 .env / 环境变量加载配置。

注意：核心字段（数据目录、端口、LLM 基础配置）用 AliasChoices 兼容旧的
`SHIGUANG_*` 环境变量，老用户 .env 不用改就能继续用。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cockpit 全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用 =====
    # 数据目录默认 ~/.shiguang（保留以兼容已有用户数据；不强制改名）
    cockpit_env: Literal["development", "production", "test"] = Field(
        default="development",
        validation_alias=AliasChoices("COCKPIT_ENV", "SHIGUANG_ENV"),
    )
    cockpit_data_dir: Path = Field(
        default=Path.home() / ".shiguang",
        validation_alias=AliasChoices("COCKPIT_DATA_DIR", "SHIGUANG_DATA_DIR"),
    )
    cockpit_port: int = Field(
        default=7842,
        validation_alias=AliasChoices("COCKPIT_PORT", "SHIGUANG_PORT"),
    )
    cockpit_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("COCKPIT_HOST", "SHIGUANG_HOST"),
    )

    # ===== LLM 后端 =====
    # 5 个后端：anthropic / deepseek / minimax / openai / custom
    # 兼容旧 SHIGUANG_LLM_BACKEND（之前是 anthropic/ollama/openai，ollama 已移除）
    cockpit_llm_backend: Literal["anthropic", "deepseek", "minimax", "openai", "custom"] = Field(
        default="anthropic",
        validation_alias=AliasChoices("COCKPIT_LLM_BACKEND", "SHIGUANG_LLM_BACKEND"),
    )
    cockpit_llm_model: str = Field(
        default="claude-sonnet-4-5",
        validation_alias=AliasChoices("COCKPIT_LLM_MODEL", "SHIGUANG_LLM_MODEL"),
    )

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL"
    )

    # DeepSeek
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    # MiniMax (MiniMax 官方 OpenAI 兼容 API)
    minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
    minimax_base_url: str = Field(
        default="https://api.minimax.chat/v1", alias="MINIMAX_BASE_URL"
    )
    minimax_model: str = Field(default="abab6.5s-chat", alias="MINIMAX_MODEL")

    # OpenAI 兼容
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="", alias="OPENAI_MODEL")

    # ===== 数据库 =====
    database_url: str = Field(default="", alias="DATABASE_URL")

    # ===== 安全 =====
    cockpit_encryption_key: str = Field(default="", alias="COCKPIT_ENCRYPTION_KEY")

    def get_database_url(self) -> str:
        """获取异步数据库 URL（默认 SQLite via aiosqlite）。"""
        if self.database_url:
            return self.database_url
        # 确保数据目录存在
        self.cockpit_data_dir.mkdir(parents=True, exist_ok=True)
        # 默认 DB 文件名保留 shiguang.db（兼容老数据；不强制改名）
        db_path = self.cockpit_data_dir / "shiguang.db"
        return f"sqlite+aiosqlite:///{db_path}"


settings = Settings()
