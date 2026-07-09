"""Anthropic Claude 客户端。

默认 LLM 后端。Claude Sonnet 4.5 中文支持好、function calling 稳定。
"""
from __future__ import annotations

import logging
from typing import Any

from app.llm.base import LLMClient, LLMResponse, ToolCall, tool_result_message

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Anthropic Claude LLM 客户端。"""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", model: str = "claude-sonnet-4-5"):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic") from e
        self._client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            resp = await self._client.messages.create(**kwargs)
        except Exception as e:
            logger.exception("Anthropic API error")
            return LLMResponse(stop_reason="error", error=str(e))

        # 解析响应
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, args=block.input or {})
                )

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=resp.stop_reason or "end_turn",
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )

    async def health_check(self) -> bool:
        """简单测试：发一个最小请求。"""
        try:
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            return len(resp.content) > 0
        except Exception:
            return False
