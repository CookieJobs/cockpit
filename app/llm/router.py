"""LLM 路由器：根据配置选择后端。

后端选择（按优先级）：
1. settings.shiguang_llm_backend
2. fallback：如果该后端不可用，尝试下一个可用后端
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.llm.base import LLMClient

logger = logging.getLogger(__name__)

_client: LLMClient | None = None
_current_backend: str | None = None


def _try_create(backend: str) -> LLMClient | None:
    """尝试创建指定后端的客户端。失败返回 None。"""
    try:
        if backend == "anthropic":
            from app.llm.anthropic import AnthropicClient
            if not settings.anthropic_api_key:
                logger.warning("ANTHROPIC_API_KEY not set")
                return None
            return AnthropicClient(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                model=settings.shiguang_llm_model,
            )
        elif backend == "ollama":
            from app.llm.ollama import OllamaClient
            return OllamaClient(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
            )
        elif backend == "openai":
            from app.llm.openai import OpenAIClient
            if not settings.openai_api_key or not settings.openai_base_url:
                logger.warning("OPENAI_API_KEY or OPENAI_BASE_URL not set")
                return None
            return OpenAIClient(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
            )
    except Exception as e:
        logger.warning(f"Failed to create {backend} client: {e}")
        return None
    return None


def get_client(prefer_backend: str | None = None) -> LLMClient | None:
    """获取 LLM 客户端（仅创建，不验证可用性）。

    优先级：
    1. prefer_backend（如果指定）
    2. settings.shiguang_llm_backend
    3. fallback：anthropic → ollama → openai

    验证 health_check 需要在 async 上下文单独调 `await client.health_check()`。
    """
    global _client, _current_backend

    if _client is not None and _current_backend == (prefer_backend or settings.shiguang_llm_backend):
        return _client

    backends_to_try = []
    if prefer_backend:
        backends_to_try.append(prefer_backend)
    backends_to_try.extend(
        b for b in ["anthropic", "ollama", "openai"]
        if b != (prefer_backend or settings.shiguang_llm_backend)
    )
    # 把用户配置的 backend 排第一（如果不是 prefer）
    if not prefer_backend and settings.shiguang_llm_backend not in backends_to_try:
        backends_to_try.insert(0, settings.shiguang_llm_backend)

    for backend in backends_to_try:
        client = _try_create(backend)
        if client is None:
            continue
        _client = client
        _current_backend = backend
        logger.info(f"LLM client initialized: {backend} ({client.model})")
        return _client

    logger.warning("No LLM client available. Fallback to keyword parser.")
    _client = None
    _current_backend = None
    return None


async def get_verified_client() -> LLMClient | None:
    """获取 LLM 客户端并验证可用性（async）。

    验证失败时尝试下一个后端。全部失败返回 None。
    """
    global _client, _current_backend

    # 先试当前缓存的
    if _client is not None:
        try:
            if await _client.health_check():
                return _client
        except Exception:
            pass
        reset_client()

    backends = ["anthropic", "ollama", "openai"]
    for backend in backends:
        client = _try_create(backend)
        if client is None:
            continue
        try:
            if await client.health_check():
                _client = client
                _current_backend = backend
                return client
        except Exception as e:
            logger.debug(f"{backend} health check failed: {e}")
            continue

    return None


def reset_client() -> None:
    """重置客户端（测试 / 配置变更时用）。"""
    global _client, _current_backend
    _client = None
    _current_backend = None
