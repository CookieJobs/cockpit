"""Ollama 本地 LLM 客户端（降级方案）。

通过 Ollama HTTP API 调本地模型（Qwen2.5、Llama3 等）。
需要本地运行 `ollama serve` 并拉取模型。

注意：Ollama 不原生支持 function calling，本实现使用 chat format 提示词
让模型自己输出结构化 JSON 作为工具调用（轻量但稳定）。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.llm.base import LLMClient, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama 本地 LLM 客户端。"""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen2.5:14b"):
        self._base_url = base_url.rstrip("/")
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
        """调 Ollama /api/chat 端点。

        Ollama 的 tool calling 支持：v0.3.0+ 支持原生 tool calling。
        """
        ollama_messages: list[dict[str, Any]] = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        ollama_messages.extend(messages)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = _convert_tools_to_ollama(tools)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self._base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.exception("Ollama API error")
            return LLMResponse(stop_reason="error", error=str(e))

        message = data.get("message", {})
        text = message.get("content", "")
        tool_calls: list[ToolCall] = []

        # Ollama 0.3.0+ 支持 tool_calls
        if "tool_calls" in message:
            for i, tc in enumerate(message["tool_calls"]):
                func = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=f"ollama-tc-{i}",
                        name=func.get("name", ""),
                        args=func.get("arguments", {}),
                    )
                )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage={},
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


def _convert_tools_to_ollama(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic 格式工具 schema → Ollama 格式。

    Ollama 0.3.0+ 接受 OpenAI 风格的 tool schema。
    """
    ollama_tools = []
    for tool in tools:
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return ollama_tools
