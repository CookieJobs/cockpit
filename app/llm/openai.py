"""OpenAI 兼容 LLM 客户端（用户自定义 endpoint）。

支持：OpenAI 官方、Azure OpenAI、DeepSeek、Moonshot 等所有 OpenAI 兼容 API。
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from app.llm.base import LLMClient, LLMResponse, StreamEvent, ToolCall

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI 兼容 LLM 客户端。"""

    def __init__(self, api_key: str, base_url: str, model: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if not base_url:
            raise ValueError("OPENAI_BASE_URL is required")
        if not model:
            raise ValueError("OPENAI_MODEL is required")
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError("openai package not installed. Run: pip install openai") from e
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
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
        # OpenAI 格式消息
        oai_messages: list[dict[str, Any]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(_convert_messages_to_openai(messages))

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
        }
        if tools:
            kwargs["tools"] = _convert_tools_to_openai(tools)
            kwargs["tool_choice"] = "auto"

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            # 不再静默剥 tools 重试 —— 剥掉 = LLM 失去工具能力，markdown
            # 兜底（chat_engine._parse_markdown_tool_calls）应该足够。
            # 上层 dispatch 会在 result.error 时自动 fallback 到 keyword 模式。
            err_msg = str(e)
            logger.exception(f"OpenAI API error (model={self._model}): {err_msg[:300]}")
            return LLMResponse(stop_reason="error", error=err_msg)

        choice = resp.choices[0] if resp.choices else None
        if not choice:
            return LLMResponse(stop_reason="error", error="No choices in response")

        text = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, args=args))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage={
                "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式 chat：text 增量 + tool_calls 完整块。

        OpenAI 流式特点：
        - text 增量通过 chunk.choices[0].delta.content 透传
        - tool_calls 是逐 index 累积的（同一 index 的 id/name/arguments
          分多个 chunk 到达），需要本地缓冲直到流结束（finish_reason）
        - 用 stream_options.include_usage 让最后一个 chunk 带 usage 统计
        """
        oai_messages: list[dict[str, Any]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        oai_messages.extend(_convert_messages_to_openai(messages))

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": oai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = _convert_tools_to_openai(tools)
            kwargs["tool_choice"] = "auto"

        # 累积 tool_calls: {index: {id, name, args_json}}
        tool_acc: dict[int, dict[str, str]] = {}
        # 累积 usage（最后一个 chunk 带）
        final_usage: dict[str, int] = {}

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                # usage chunk（无 choices，仅 usage）
                if chunk.usage is not None:
                    final_usage = {
                        "input_tokens": chunk.usage.prompt_tokens or 0,
                        "output_tokens": chunk.usage.completion_tokens or 0,
                    }
                    continue
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                # text 增量
                content = getattr(delta, "content", None)
                if content:
                    yield {"type": "text", "data": {"delta": content}}
                # tool_calls 累积（同一 index 多 chunk）
                tcs = getattr(delta, "tool_calls", None)
                if tcs:
                    for tc in tcs:
                        idx = tc.index
                        if idx not in tool_acc:
                            tool_acc[idx] = {"id": "", "name": "", "args_json": ""}
                        if tc.id:
                            tool_acc[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_acc[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_acc[idx]["args_json"] += tc.function.arguments
                # finish_reason 仅作为信号，不主动 emit（流结束由循环退出表达）
                _ = choice.finish_reason

            # 流结束：emit 所有 tool_start（按 index 顺序）
            for idx in sorted(tool_acc.keys()):
                tc = tool_acc[idx]
                raw = tc["args_json"]
                try:
                    args = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to parse tool args JSON for {tc['name']}: {raw[:200]}"
                    )
                    args = {"_raw": raw}
                yield {
                    "type": "tool_start",
                    "data": {
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": args,
                    },
                }
            # usage（如果有）—— 通过 end 事件透传，但 chat_engine 不消费这个，
            # 实际持久化时可以从 chat_engine 端重新累加。略。
        except Exception as e:
            err_msg = str(e)
            logger.exception(f"OpenAI stream error (model={self._model}): {err_msg[:300]}")
            yield {"type": "error", "data": {"message": f"OpenAI stream error: {err_msg}"}}

    async def health_check(self) -> bool:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return bool(resp.choices)
        except Exception:
            return False


def _convert_messages_to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic 格式消息 → OpenAI 格式。

    主要差异：
    - tool_result 在 OpenAI 是 role="tool" 单条消息
    - Anthropic 的 content 是 list of blocks，OpenAI 的 content 是 string
      （除多模态外）。这里把所有 list content 合并成 string
      （拼接 text blocks，丢弃 tool_use blocks——它们应该是 assistant 消息的 tool_calls 字段）
    - assistant 消息的 content list 含 type: "tool_use" 时，转成 OpenAI tool_calls 格式
    """
    result: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "user" and isinstance(content, list):
            # user 的 list content 可能是 text + tool_result
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    result.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block.get("content", ""),
                    })
                else:
                    # 其他 block 当文本
                    text = block.get("text", "") if isinstance(block, dict) else str(block)
                    if text:
                        result.append({"role": "user", "content": text})
        elif role == "assistant" and isinstance(content, list):
            # assistant 的 list content：text blocks 合并成字符串，tool_use 转 tool_calls
            text_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        # 转换成 OpenAI tool_calls 格式
                        tool_calls.append({
                            "id": block.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                            },
                        })
            new_msg: dict[str, Any] = {"role": "assistant", "content": "".join(text_parts)}
            if tool_calls:
                new_msg["tool_calls"] = tool_calls
            result.append(new_msg)
        else:
            # 普通消息：content 是字符串（或其他基本类型）
            new_msg: dict[str, Any] = {"role": role, "content": content}
            # 如果是 assistant 且有 tool_calls，要补回去（兼容旧调用）
            if role == "assistant" and "tool_calls" in msg:
                new_msg["tool_calls"] = msg["tool_calls"]
            result.append(new_msg)
    return result


def _convert_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic 工具 schema → OpenAI 工具 schema。"""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]
