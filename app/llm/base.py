"""LLM 抽象层：统一协议，多后端实现。

支持：
- Anthropic Claude（默认）
- Ollama（本地降级）
- OpenAI 兼容（用户自定义 endpoint）

所有实现都返回统一的 LLMResponse 格式（text + tool_calls + stop_reason）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


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
