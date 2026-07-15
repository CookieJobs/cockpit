"""Anthropic Claude 客户端。

默认 LLM 后端。Claude Sonnet 4.5 中文支持好、function calling 稳定。
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from app.llm.base import LLMClient, LLMResponse, StreamEvent, ToolCall, tool_result_message

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

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式 chat：text 增量 + tool_use 完整块。

        Anthropic SDK 的 stream manager 提供低层事件流：
        - content_block_start: 块开始（text / tool_use）
        - content_block_delta: 块增量（text_delta / input_json_delta）
        - content_block_stop: 块结束
        - message_delta / message_stop: 消息级事件
        - ping: 心跳（忽略）

        我们把 text_delta 透传为 text 事件；tool_use 块通过累积
        input_json_delta → content_block_stop 时一次性 yield tool_start 事件。
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        # 当前累积的 tool_use 块
        current_tool: dict[str, Any] | None = None

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    et = getattr(event, "type", None)
                    if et == "content_block_start":
                        block = event.content_block
                        btype = getattr(block, "type", None)
                        if btype == "tool_use":
                            current_tool = {
                                "id": block.id,
                                "name": block.name,
                                "args_json": "",
                            }
                        # text 块无需预处理
                    elif et == "content_block_delta":
                        delta = event.delta
                        dtype = getattr(delta, "type", None)
                        if dtype == "text_delta":
                            text = getattr(delta, "text", "")
                            if text:
                                yield {"type": "text", "data": {"delta": text}}
                        elif dtype == "input_json_delta":
                            if current_tool is not None:
                                pj = getattr(delta, "partial_json", "")
                                if pj:
                                    current_tool["args_json"] += pj
                    elif et == "content_block_stop":
                        if current_tool is not None:
                            raw = current_tool["args_json"]
                            try:
                                args = json.loads(raw) if raw else {}
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Failed to parse tool args JSON for {current_tool['name']}: {raw[:200]}"
                                )
                                args = {"_raw": raw}
                            yield {
                                "type": "tool_start",
                                "data": {
                                    "id": current_tool["id"],
                                    "name": current_tool["name"],
                                    "args": args,
                                },
                            }
                            current_tool = None
                    # 其它事件（message_start / message_delta / message_stop / ping）忽略
        except Exception as e:
            logger.exception("Anthropic stream error")
            yield {"type": "error", "data": {"message": f"Anthropic stream error: {e}"}}

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
