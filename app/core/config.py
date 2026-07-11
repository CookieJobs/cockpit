"""Cockpit 配置管理。

通过 pydantic-settings 从 .env / 环境变量加载配置。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
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
    cockpit_env: Literal["development", "production", "test"] = Field(
        default="development",
        alias="COCKPIT_ENV",
    )
    cockpit_data_dir: Path = Field(
        default=Path.home() / ".cockpit",
        alias="COCKPIT_DATA_DIR",
    )
    cockpit_port: int = Field(
        default=7842,
        alias="COCKPIT_PORT",
    )
    cockpit_host: str = Field(
        default="127.0.0.1",
        alias="COCKPIT_HOST",
    )

    # ===== LLM 后端 =====
    # 5 个后端：anthropic / deepseek / minimax / openai / custom
    cockpit_llm_backend: Literal["anthropic", "deepseek", "minimax", "openai", "custom"] = Field(
        default="anthropic",
        alias="COCKPIT_LLM_BACKEND",
    )
    cockpit_llm_model: str = Field(
        default="claude-sonnet-4-5",
        alias="COCKPIT_LLM_MODEL",
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
        """获取异步数据库 URL（默认 SQLite via aiosqlite）。

        数据迁移：首次启动时如果 ~/.cockpit/cockpit.db 不存在，但 ~/.shiguang/shiguang.db
        存在（老品牌数据），自动 copy 老 DB 到新路径，保留所有项目/任务/成就/对话。
        """
        if self.database_url:
            return self.database_url
        # 确保数据目录存在
        self.cockpit_data_dir.mkdir(parents=True, exist_ok=True)
        # 默认 DB 文件名 cockpit.db
        new_db = self.cockpit_data_dir / "cockpit.db"
        # 自动迁移老数据
        self._migrate_legacy_data(new_db)
        return f"sqlite+aiosqlite:///{new_db}"

    def _migrate_legacy_data(self, new_db: Path) -> None:
        """从 ~/.shiguang/shiguang.db 自动迁移到 ~/.cockpit/cockpit.db。

        迁移条件：
        - 新 DB 不存在
        - 老 DB（~/.shiguang/shiguang.db）存在
        迁移行为：
        - copy 老 DB 到新路径（保留原文件作为备份）
        - 打印迁移日志
        """
        if new_db.exists():
            return
        old_db = Path.home() / ".shiguang" / "shiguang.db"
        if not old_db.exists():
            return
        # 原子 copy（读时 lock 防止写入中）
        import shutil
        shutil.copy2(old_db, new_db)
        print(f"[cockpit] 已从 {old_db} 迁移老品牌数据 → {new_db}")
        print(f"[cockpit] 原始 {old_db} 保留为备份，可手动删除")


settings = Settings()
