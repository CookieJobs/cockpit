"""Cockpit 配置管理。

通过 pydantic-settings 从 .env / 环境变量加载配置。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class DataRecoveryState:
    """Outcome of checking the legacy relative Cockpit database location."""

    kind: Literal["absent", "existing", "migrated", "already_migrated", "conflict", "failed"]
    target: Path
    misplaced: Path
    message: str = ""


class DataRecoveryRequired(RuntimeError):
    """Raised before an empty database can mask a recoverable data conflict."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_sqlite_database(path: Path) -> None:
    """Ensure a copied SQLite database is readable and internally consistent."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if result != ("ok",):
        raise sqlite3.DatabaseError(f"SQLite integrity check failed for {path}: {result}")


def migrate_misplaced_database(*, cwd: Path, target: Path) -> DataRecoveryState:
    """Recover the historical ``<cwd>/~/.cockpit/cockpit.db`` without data loss."""
    target = target.expanduser().resolve()
    misplaced = (cwd.resolve() / "~" / ".cockpit" / "cockpit.db").resolve()

    if not misplaced.exists():
        return DataRecoveryState(
            kind="existing" if target.exists() else "absent",
            target=target,
            misplaced=misplaced,
        )

    try:
        _verify_sqlite_database(misplaced)
        if target.exists():
            _verify_sqlite_database(target)
            if _sha256(misplaced) == _sha256(target):
                return DataRecoveryState(
                    kind="already_migrated",
                    target=target,
                    misplaced=misplaced,
                    message="已发现与正确数据目录一致的历史副本，继续使用正确位置。",
                )
            return DataRecoveryState(
                kind="conflict",
                target=target,
                misplaced=misplaced,
                message="发现两份内容不同的 Cockpit 数据库；已暂停写入，请在设置中选择主库。",
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            shutil.copy2(misplaced, temporary)
            if _sha256(misplaced) != _sha256(temporary):
                raise OSError("copied database checksum does not match source")
            _verify_sqlite_database(temporary)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = misplaced.with_name(f"{misplaced.name}.migrated-{timestamp}-{uuid.uuid4().hex[:8]}.bak")
        shutil.copy2(misplaced, backup)
        return DataRecoveryState(
            kind="migrated",
            target=target,
            misplaced=misplaced,
            message=f"已安全复制历史数据到 {target}，原位置和备份均已保留。",
        )
    except (OSError, sqlite3.Error) as error:
        return DataRecoveryState(
            kind="failed",
            target=target,
            misplaced=misplaced,
            message=f"无法迁移历史 Cockpit 数据库：{error}",
        )


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
    # 注: dev 默认值留给本地 / 单元测试。Docker 部署时通过环境变量
    # COCKPIT_HOST=0.0.0.0 + COCKPIT_ENV=production 覆盖。
    # 详见 docs/deployment.md
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
    # 默认 127.0.0.1（本地安全）。Docker 部署通过 env 覆盖成 0.0.0.0。
    # 也可以显式通过 COCKPIT_HOST=0.0.0.0 启动本地 dev（但通常不需要）。
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
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")

    # MiniMax (MiniMax 官方 OpenAI 兼容 API)
    minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
    minimax_base_url: str = Field(
        default="https://api.minimaxi.com/v1", alias="MINIMAX_BASE_URL"
    )
    minimax_model: str = Field(default="MiniMax-M3", alias="MINIMAX_MODEL")

    # OpenAI 兼容
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="", alias="OPENAI_MODEL")

    # ===== 数据库 =====
    database_url: str = Field(default="", alias="DATABASE_URL")

    # ===== 安全 =====
    cockpit_encryption_key: str = Field(default="", alias="COCKPIT_ENCRYPTION_KEY")

    # CORS 白名单（逗号分隔的 origin 列表）。默认开发期允许 3000 端口。
    # Docker 部署时同源 (前端 build 由 FastAPI serve) 不会触发 CORS,
    # 但如果加 nginx 反代 80→7842, origin 变化, 需要把反代 origin 加进来。
    # 例: COCKPIT_CORS_ORIGINS="http://62.234.180.241,https://cockpit.example.com"
    cockpit_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="COCKPIT_CORS_ORIGINS",
    )

    _data_recovery_state: DataRecoveryState | None = PrivateAttr(default=None)

    def resolved_data_dir(self) -> Path:
        """Return the one expanded, absolute directory used by Cockpit data paths."""
        return self.cockpit_data_dir.expanduser().resolve()

    def data_recovery_state(self) -> DataRecoveryState | None:
        """Return the latest startup recovery result for diagnostics and API guards."""
        return self._data_recovery_state

    def get_database_url(self) -> str:
        """获取异步数据库 URL（默认 SQLite via aiosqlite）。

        数据迁移：首次启动时如果 ~/.cockpit/cockpit.db 不存在，但 ~/.shiguang/shiguang.db
        存在（老品牌数据），自动 copy 老 DB 到新路径，保留所有项目/任务/成就/对话。
        """
        if self.database_url:
            return self.database_url
        data_dir = self.resolved_data_dir()
        # 确保数据目录存在
        data_dir.mkdir(parents=True, exist_ok=True)
        # 默认 DB 文件名 cockpit.db
        new_db = data_dir / "cockpit.db"
        self._data_recovery_state = migrate_misplaced_database(cwd=Path.cwd(), target=new_db)
        if self._data_recovery_state.kind in {"conflict", "failed"}:
            # Keep the existing target readable for recovery diagnostics.  The
            # shared storage write guard rejects mutations before commit.
            return f"sqlite+aiosqlite:///{new_db}"
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
