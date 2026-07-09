"""LLM 配置管理：DB 用户配置 > .env > 默认。

优先级：
1. settings 表里的 "llm_config"（用户从 UI 配的）
2. .env 文件里的 SHIGUANG_LLM_BACKEND / ANTHROPIC_API_KEY 等
3. 默认值（anthropic + claude-sonnet-4-5）

修改 DB 配置后，调用 reset_client() 清缓存，下一次 get_client() 会用新配置。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.core import storage
from app.core.config import settings
from app.core.models import LLMSettings
from app.llm.base import LLMClient

logger = logging.getLogger(__name__)

DB_CONFIG_KEY = "llm_config"

_client: LLMClient | None = None
_current_backend: str | None = None


# ===== 配置读取 =====


async def load_settings_from_db() -> Optional[LLMSettings]:
    """从 DB 读用户配置。如果配置无效（用了过时的后端类型），自动清理。"""
    raw = await storage.get_setting(DB_CONFIG_KEY)
    if not raw:
        return None
    try:
        return LLMSettings.model_validate_json(raw)
    except Exception as e:
        logger.warning(f"Invalid LLM settings in DB, cleaning up: {e}")
        # 自动清理过时配置（如旧 ollama 类型）
        await storage.delete_setting(DB_CONFIG_KEY)
        return None


def load_settings_from_env() -> LLMSettings:
    """从 .env 读配置（fallback）。"""
    backend = settings.shiguang_llm_backend
    if backend == "anthropic":
        return LLMSettings(
            backend=backend,
            model=settings.shiguang_llm_model,
            api_key=settings.anthropic_api_key or None,
            base_url=settings.anthropic_base_url,
        )
    elif backend in ("deepseek", "minimax", "openai", "custom"):
        # 都走 OpenAI 兼容协议
        return LLMSettings(
            backend=backend,
            model=settings.openai_model or "gpt-4o",
            api_key=settings.openai_api_key or None,
            base_url=settings.openai_base_url or None,
        )
    else:
        return LLMSettings(
            backend=backend,
            model=settings.shiguang_llm_model,
        )


async def get_active_settings() -> LLMSettings:
    """获取当前生效的 LLM 配置（DB 优先，回退到 env）。"""
    db_settings = await load_settings_from_db()
    if db_settings is not None:
        return db_settings
    return load_settings_from_env()


async def get_active_settings_with_source() -> tuple[LLMSettings, str]:
    """获取配置 + 来源标识。"""
    db_settings = await load_settings_from_db()
    if db_settings is not None:
        return db_settings, "db"
    return load_settings_from_env(), "env"


# ===== 客户端创建 =====


def _try_create_from_settings(cfg: LLMSettings) -> LLMClient | None:
    """根据配置创建 LLM 客户端。"""
    try:
        if cfg.backend == "anthropic":
            from app.llm.anthropic import AnthropicClient
            if not cfg.api_key:
                logger.warning("Anthropic backend requires api_key")
                return None
            return AnthropicClient(
                api_key=cfg.api_key,
                base_url=cfg.base_url or "https://api.anthropic.com",
                model=cfg.model,
            )
        elif cfg.backend in ("deepseek", "minimax", "openai", "custom"):
            # 都走 OpenAI 兼容协议
            from app.llm.openai import OpenAIClient
            if not cfg.api_key:
                logger.warning(f"{cfg.backend} backend requires api_key")
                return None
            if not cfg.base_url:
                logger.warning(f"{cfg.backend} backend requires base_url")
                return None
            return OpenAIClient(
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                model=cfg.model,
            )
    except Exception as e:
        logger.warning(f"Failed to create {cfg.backend} client: {e}")
        return None
    return None


def get_client(prefer_backend: str | None = None) -> LLMClient | None:
    """同步获取客户端（用上次缓存的配置）。

    实际使用建议用 get_verified_client() 异步版。
    """
    global _client, _current_backend
    if _client is not None and prefer_backend is None:
        return _client
    # 同步 fallback：先尝试 .env 配置
    env_cfg = load_settings_from_env()
    return _try_create_from_settings(env_cfg)


async def get_verified_client() -> LLMClient | None:
    """异步：获取 LLM 客户端并验证可用性。

    优先级：
    1. DB 用户配置（如果存在）
    2. .env 配置
    3. 全部失败返回 None
    """
    global _client, _current_backend

    # 先用缓存的（如果还是有效）
    if _client is not None:
        try:
            if await _client.health_check():
                return _client
        except Exception:
            pass
        reset_client()

    # 1. 试 DB 配置
    db_cfg = await load_settings_from_db()
    if db_cfg is not None:
        client = _try_create_from_settings(db_cfg)
        if client is not None:
            try:
                if await client.health_check():
                    _client = client
                    _current_backend = db_cfg.backend.value
                    logger.info(f"LLM client from DB: {db_cfg.backend.value}/{db_cfg.model}")
                    return _client
            except Exception as e:
                logger.debug(f"DB-configured client failed health check: {e}")

    # 2. fallback 到 env 配置
    env_cfg = load_settings_from_env()
    client = _try_create_from_settings(env_cfg)
    if client is not None:
        try:
            if await client.health_check():
                _client = client
                _current_backend = env_cfg.backend.value
                logger.info(f"LLM client from env: {env_cfg.backend.value}/{env_cfg.model}")
                return _client
        except Exception as e:
            logger.debug(f"env-configured client failed health check: {e}")

    return None


def reset_client() -> None:
    """重置客户端缓存（配置变更后用）。"""
    global _client, _current_backend
    _client = None
    _current_backend = None
