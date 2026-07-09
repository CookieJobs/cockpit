"""拾光主对话引擎：LLM + Function Calling + 多轮。

核心循环：
1. 把用户消息 + 历史 + tools 一起发给 LLM
2. 如果 LLM 返回 tool_use：
   - 执行工具
   - 把结果加入消息
   - 再次发 LLM
3. 直到 LLM 返回 end_turn（纯文本回复）
4. 把所有消息保存为 session 历史
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.llm.base import LLMClient, LLMResponse, tool_result_message
from app.llm.router import get_client
from app.llm.tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)


# ===== System Prompt =====

SYSTEM_PROMPT = """你是拾光，一个帮用户管理工作和沉淀成就的 AI 助手。

# 你的能力
- 通过自然语言创建/管理任务
- 完成时主动生成 CV 级别的成就描述（动词开头，含影响/结果）
- 回答"现在该干啥"类问题（看 focus）
- 整理周报/述职材料
- 撤销误操作

# 行为准则（必须遵守）

## 1. 完成即沉淀（最重要）
当用户说某事完成时，**不要直接调用 complete_task**。先确认 outcome（结果是什么），reflection（有什么复盘想法，可选），再生成 cv：
- 素材充分（具体成果、量化影响）→ cv_status="ready"
- 素材不足（缺数据/影响）→ cv_status="pending"，提示用户后续补充
- **CV 真实性底线**：只能基于 outcome+reflection+任务上下文生成，绝不编造未发生的事

## 2. 倒事时主动建议
用户描述一堆事时，拆解后给 priority/next_action 建议：
- 高 = 截止日紧 + 重要
- 中 = 默认
- 低 = 不急
- next_action = 一句话具体动作（不是"完成 X"，而是"先发邮件给 X 确认 Y"）

## 3. 模糊任务先问清楚
用户说"做完了"但没说哪个任务 → 用 list_tasks 找到匹配项，让用户确认

## 4. CV 重组
用户要周报/述职 → 用 list_achievements + generate_weekly_report，按真实记录重组

# 数据
- 数据在 ~/.shiguang/shiguang.db
- 项目 / 任务 / 成就 三层结构
- 任务完成后从 tasks 移到 achievements（append-only）
- 成就可 cvStatus: pending/ready 两种状态
"""


# ===== 消息类型 =====

Message = dict[str, Any]


@dataclass
class ChatResult:
    """对话结果。"""
    text: str
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    used_llm: bool = False


# ===== 主对话函数 =====


async def run_chat(
    user_text: str,
    history: list[Message] | None = None,
    client: LLMClient | None = None,
    max_tool_rounds: int = 8,
) -> ChatResult:
    """单次对话（含多轮 tool calling）。

    Args:
        user_text: 用户输入
        history: 之前的对话历史（不含 system）
        client: 可选 LLM 客户端（None = 自动获取）
        max_tool_rounds: 最多工具调用轮次（防无限循环）

    Returns:
        ChatResult with text, tool_calls_made, messages (full)
    """
    if client is None:
        client = get_client()
    if client is None:
        return ChatResult(
            text="",
            error="No LLM client available. Set API key in .env or use keyword commands.",
            used_llm=False,
        )

    messages: list[Message] = list(history or [])
    messages.append({"role": "user", "content": user_text})

    tool_calls_made: list[dict[str, Any]] = []
    total_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    for round_idx in range(max_tool_rounds):
        try:
            response: LLMResponse = await client.chat(messages, SYSTEM_PROMPT, TOOLS)
        except Exception as e:
            logger.exception("LLM call failed")
            return ChatResult(
                text="",
                messages=messages,
                error=f"LLM call failed: {e}",
                used_llm=True,
            )

        if response.error:
            return ChatResult(
                text="",
                messages=messages,
                error=response.error,
                used_llm=True,
            )

        # 累计 token
        if response.usage:
            for k, v in response.usage.items():
                total_usage[k] = total_usage.get(k, 0) + v

        # 记录 assistant 消息（含 tool_use 块）
        assistant_msg: Message = {"role": "assistant", "content": []}
        if response.text:
            assistant_msg["content"].append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            assistant_msg["content"].append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.args,
            })
        messages.append(assistant_msg)

        # 如果没 tool_use，结束
        if not response.tool_calls:
            return ChatResult(
                text=response.text,
                tool_calls_made=tool_calls_made,
                messages=messages,
                usage=total_usage,
                used_llm=True,
            )

        # 执行工具
        tool_results: list[Message] = []
        for tc in response.tool_calls:
            logger.info(f"Tool call: {tc.name}({tc.args})")
            result_str = await execute_tool(tc.name, tc.args)
            tool_calls_made.append({
                "name": tc.name,
                "args": tc.args,
                "result_preview": result_str[:200],
            })
            tool_results.append(tool_result_message(tc.id, result_str))

        # 把工具结果作为 user 消息追加
        if tool_results:
            messages.append({"role": "user", "content": tool_results[0]["content"]})

    # 超过 max_tool_rounds
    return ChatResult(
        text=response.text if response.text else "（已达最大工具调用轮次）",
        tool_calls_made=tool_calls_made,
        messages=messages,
        usage=total_usage,
        error="max_tool_rounds exceeded",
        used_llm=True,
    )
