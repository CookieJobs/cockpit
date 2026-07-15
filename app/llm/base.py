"""LLM 抽象层：统一协议，多后端实现。

支持：
- Anthropic Claude（默认）
- Ollama（本地降级）
- OpenAI 兼容（用户自定义 endpoint）

所有实现都返回统一的 LLMResponse 格式（text + tool_calls + stop_reason）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


@dataclass
class ToolCall:
    """LLM 请求调用工具的描述。"""
    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 单次返回结果。"""
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens" | "error"
    error: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


# ===== 流式事件协议 =====
#
# 流式 chat 走 async generator，yield dict（type + data），前后端统一契约。
# 事件类型：
#   {"type": "text",         "data": {"delta": "..."}}         文本增量
#   {"type": "tool_start",   "data": {"id", "name", "args"}}  工具调用开始（含参数）
#   {"type": "tool_end",     "data": {"id", "result", "ok"}}  工具调用结束（含结果）
#   {"type": "error",        "data": {"message": "..."}}      错误（流式终止信号）
#
# 注意：chat_engine.run_chat_stream 内部不 yield start/end —— start/end 由
# API 层（app/api/chat.py 的 /api/chat/stream）统一管理，因为 API 层才知道
# session_id 和持久化结果。

StreamEvent = dict[str, Any]


class LLMClient(Protocol):
    """LLM 客户端协议。所有后端都实现这个接口。"""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """单次 LLM 调用（含 tool calling）。

        messages: 标准消息列表 [{"role": "user"|"assistant"|"tool", "content": ...}]
        system: 系统提示词
        tools: 工具 schema 列表（Anthropic 格式）

        返回 LLMResponse，包含 text 和/或 tool_calls。
        """
        ...

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式 LLM 调用。

        yield StreamEvent 序列（text / tool_start / tool_end / error）。
        错误时 yield 最后一个 error 事件后正常返回（不再抛异常），由
        上层决定是否终结流。
        """
        ...

    async def health_check(self) -> bool:
        """检查 LLM 后端是否可达 + 凭证有效。"""
        ...


def tool_result_message(tool_call_id: str, result: Any) -> dict[str, Any]:
    """构造 tool_result 消息（Anthropic 格式）。"""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": str(result),
            }
        ],
    }


def text_message(role: str, text: str) -> dict[str, Any]:
    """构造纯文本消息。"""
    return {"role": role, "content": text}
