"""Cockpit主对话引擎：LLM + Function Calling + 多轮。

核心循环：
1. 把用户消息 + 历史 + tools 一起发给 LLM
2. 如果 LLM 返回 tool_use：
   - 执行工具
   - 把结果加入消息
   - 再次发 LLM
3. 直到 LLM 返回 end_turn（纯文本回复）
4. 把所有消息保存为 session 历史

流式版本（run_chat_stream）：同样循环，但通过 async generator 边吐事件
（text / tool_start / tool_end）边推进。start/end 事件由调用方管理。
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.llm.base import LLMClient, LLMResponse, StreamEvent, ToolCall, tool_result_message
from app.llm.prompts import SYSTEM_PROMPT  # 2026-07-22 抽: 原本是 235 行三引号字符串, 现在 .md 加载
from app.llm.router import get_client
from app.llm.tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)


# ===== Markdown tool call fallback =====


# 匹配 markdown code block 里的 functions.name(args) 调用
# 例：`functions.add_task({"title": "..."})`、`functions.add_project("项目交接")`、`functions.list_projects()`
_MARKDOWN_TOOL_CALL_RE = re.compile(
    r"functions\.(\w+)\s*\(\s*(\{.*?\}|[^)]*)\s*\)",
    re.DOTALL,
)

# 允许 markdown fallback 解析的工具（防止误解析无关文本）
_MARKDOWN_TOOL_WHITELIST = {
    "add_project",
    "add_task",
    "update_task",
    "update_project",
    "delete_project",
    "delete_task",
    "list_projects",
    "list_tasks",
    "complete_task",
    "query_snapshot",
}


# 匹配 LLM 内部的 CoT 思维链块。DeepSeek R1 / MiniMax M3 等推理模型
# 倾向在 content 字段里写 `<think>...</think>` / `<thinking>...</thinking>` /
# `<reasoning>...</reasoning>`，必须先剥离再走下游处理（特别是 markdown
# tool call fallback —— CoT 里的 `functions.delete_task(...)` 不应该被当真）。
_THINK_BLOCK_RE = re.compile(
    r"<\s*(?:think|thinking|reasoning)\b[^>]*>.*?<\s*/\s*(?:think|thinking|reasoning)\s*>",
    re.DOTALL | re.IGNORECASE,
)
# 流式版额外需要：open / close 标签单独匹配（用于检测未关闭的 think 块）
_THINK_OPEN_RE = re.compile(
    r"<\s*(?:think|thinking|reasoning)\b[^>]*>",
    re.IGNORECASE,
)
_THINK_CLOSE_RE = re.compile(
    r"<\s*/\s*(?:think|thinking|reasoning)\s*>",
    re.IGNORECASE,
)


def strip_think_blocks(text: str) -> str:
    """剥离 LLM CoT 思维链块。

    适用于：DeepSeek R1、DeepSeek V3.x 推理模式、MiniMax M3、MiniMax-M3 等
    在 content 字段写 `<think>...</think>` 的国产推理模型。

    注意：替换为单个空格而不是空串 —— 避免两个相邻 think 块 / think 块
    紧贴正文时把前后 token 粘到一起。

    **重要限制**：这个函数假设传入完整文本（think 块已关闭）。
    流式场景（think 块跨多个 delta）请用 `strip_think_blocks_incremental`。
    """
    if not text:
        return text
    return _THINK_BLOCK_RE.sub(" ", text).strip()


def strip_think_blocks_incremental(text: str) -> str:
    """流式版 strip think 块。

    区别于 `strip_think_blocks`：当 think 块未关闭时（`<think>` 已出现但
    `</think>` 还没到），会把从 `<think>` 起到末尾全丢掉（避免 think 块
    的前缀内容泄露到 UI）。

    用法：每次拿到新的累计 raw text 跑一次，与上一次 stripped 末尾取
    差量 emit。
    """
    if not text:
        return text
    # 1. 剥所有完整块
    out = _THINK_BLOCK_RE.sub(" ", text)
    # 2. 检查是否还残留未关闭的 think open 标签
    # 找最后一个 open 标签
    last_open = None
    for m in _THINK_OPEN_RE.finditer(out):
        last_open = m
    if last_open is not None:
        # 在 last_open 之后找 close
        if not _THINK_CLOSE_RE.search(out, last_open.end()):
            # 未关闭：从 last_open 之前截断
            out = out[: last_open.start()]
    return out.strip()


def _parse_markdown_tool_calls(text: str) -> list[ToolCall]:
    """从 LLM 输出的 markdown 文本中提取伪 tool call。

    适用场景：部分国产模型（旧版 MiniMax abab 系列等）在拿到 tool_result
    后倾向于输出 `functions.xxx(args)` markdown code block 而不是真的调
    tool_use。M3/M2.7 等新模型理论上不需要此 fallback，但保留以兜底。

    Returns:
        解析出的 ToolCall 列表（白名单内的工具才返回）
    """
    if not text:
        return []
    calls: list[ToolCall] = []
    seen: set[str] = set()  # 去重：同一 call_id 不重复
    for match in _MARKDOWN_TOOL_CALL_RE.finditer(text):
        name, raw_args = match.group(1), match.group(2).strip()
        if name not in _MARKDOWN_TOOL_WHITELIST:
            continue
        # 解析 args
        try:
            if not raw_args:
                # 空参数：functions.list_projects()
                args = {}
            elif raw_args.startswith("{"):
                args = json.loads(raw_args)
            else:
                # 裸字符串：functions.add_project("项目交接")
                args = {"name": raw_args.strip("\"'")}
        except json.JSONDecodeError:
            continue
        # 去重
        sig = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        if sig in seen:
            continue
        seen.add(sig)
        calls.append(ToolCall(
            id=f"md-{uuid.uuid4().hex[:12]}",
            name=name,
            args=args,
        ))
    return calls


# ===== System Prompt =====
# 2026-07-22 抽: SYSTEM_PROMPT 已抽到 app/llm/prompts/cockpit_system.md,
# 上面 import 直接拿到。改 prompt 只动 .md 文件, 不需要碰 .py。


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

        # 剥离 LLM CoT 思维链块（DeepSeek R1 / MiniMax M3 等会把
        # 推理过程写在 content 里）。必须在所有下游处理之前做：
        # 1. 避免存到 messages / 持久化 / 前端显示 —— 用户不该看到 CoT
        # 2. 避免 markdown fallback 把 CoT 里的 `functions.delete_task(...)`
        #    当真工具调用执行（这是潜在的不可逆数据丢失路径）
        response.text = strip_think_blocks(response.text)

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
            # Fallback: 某些模型（旧 MiniMax abab 系列等）在拿到 tool_result 后
            # 倾向于输出 markdown 伪 tool call（`functions.add_task(...)`）而不是
            # 真的调 tool_use。检测并执行，提升主动性。M3/M2.7 通常不需要，但保留兜底。
            markdown_calls = _parse_markdown_tool_calls(response.text)
            if markdown_calls:
                logger.info(
                    f"Markdown fallback: parsed {len(markdown_calls)} tool calls from text"
                )
                response.tool_calls = markdown_calls
                # 继续循环，让这些 tool calls 执行
                # 但 assistant_msg 已经 append 了（不含 tool_use 块），继续往下走
                # tool_use 块需要补回去
                for tc in response.tool_calls:
                    assistant_msg["content"].append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.args,
                    })
                # 更新 messages 里的 assistant_msg（之前 append 的没含 tool_use）
                messages[-1] = assistant_msg
            else:
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
        # 合并所有 tool_result blocks 到同一条 user 消息 ——
        # 一次 round 可能并行调多个 tool（系统 prompt 鼓励），
        # 上一条 assistant_msg 已经 append 了 N 个 tool_use blocks，
        # 必须把所有 N 个 tool_result 一起回传，否则 LLM 报
        # "tool call and result not match" (MiniMax-M3 是 2013)。
        if tool_results:
            combined_blocks: list[dict[str, Any]] = []
            for tr in tool_results:
                # tr 是 Anthropic 格式 {"role": "user", "content": [{type: tool_result, ...}]}
                # 把 content list 里的所有 block 平铺进去
                if isinstance(tr.get("content"), list):
                    combined_blocks.extend(tr["content"])
                else:
                    combined_blocks.append(tr["content"])
            messages.append({"role": "user", "content": combined_blocks})

    # 超过 max_tool_rounds
    return ChatResult(
        text=response.text if response.text else "（已达最大工具调用轮次）",
        tool_calls_made=tool_calls_made,
        messages=messages,
        usage=total_usage,
        error="max_tool_rounds exceeded",
        used_llm=True,
    )


# ===== 流式版本 =====


async def run_chat_stream(
    user_text: str,
    history: list[Message] | None = None,
    client: LLMClient | None = None,
    max_tool_rounds: int = 8,
    prefer_llm: bool = True,
) -> AsyncIterator[StreamEvent]:
    """流式单次对话（含多轮 tool calling + 关键词 fallback）。

    行为与 run_chat 一致（LLM 优先 / 失败自动 fallback 关键词 / 可选
    prefer_llm=False 强制走关键词），但通过 async generator 边推进边
    yield 事件：
    - {"type": "text", "data": {"delta": "..."}} — 文本增量（已 strip CoT）
    - {"type": "tool_start", "data": {"id", "name", "args"}} — 工具开始
    - {"type": "tool_end", "data": {"id", "result", "ok"}} — 工具结束
    - {"type": "cot", "data": {"text": "<think>...</think>"}} — CoT 块
      完成时（API 层捕获，**不**透传给客户端，用于填到 end 事件）
    - {"type": "error", "data": {"message": "..."}} — 错误（流终止信号）

    **不** yield start/end —— 由 API 层（app/api/chat.py）统一管理。

    CoT 处理：text 事件是**已 strip** 的相对增量。具体做法是每收到
    raw delta，累积到 round_text_raw → 跑一次 strip_think_blocks →
    取与上一份 stripped 末尾的差量 emit。同时，原始 round_text_raw
    上的完整 think 块被捕获并 yield `cot` 事件，让 API 层在 end 事件
    里带上完整的 CoT 原文（用于"显示 CoT"开关）。
    """
    # 1. 决定走 LLM 还是关键词
    if prefer_llm:
        if client is None:
            client = get_client()
        if client is None:
            # LLM 不可用 → fallback 关键词
            logger.info("No LLM client, falling back to keyword stream")
            async for ev in _run_keyword_stream(user_text):
                yield ev
            return
    else:
        # 强制走关键词
        async for ev in _run_keyword_stream(user_text):
            yield ev
        return

    # 2. 走 LLM 流式
    messages: list[Message] = list(history or [])
    messages.append({"role": "user", "content": user_text})

    tool_calls_made: list[dict[str, Any]] = []

    for round_idx in range(max_tool_rounds):
        # 本轮累积（已 strip 视角）
        round_text_raw = ""
        round_text_clean = ""
        round_tool_calls: list[ToolCall] = []
        # 本轮已 yield 过的完整 think 块（用 set 去重 —— 用位置/长度
        # 跟踪不可靠，因为 think 块在累积到 </think> 时可能跨越位置边界，
        # raw[offset:] 切片会截断整块）
        round_yielded_cot: set[str] = set()

        try:
            async for event in client.stream_chat(messages, SYSTEM_PROMPT, TOOLS):
                etype = event.get("type")
                if etype == "text":
                    delta = event["data"]["delta"]
                    round_text_raw += delta
                    # 1) 捕获新增的完整 think 块，yield cot 事件
                    for m in _THINK_BLOCK_RE.finditer(round_text_raw):
                        block_text = m.group(0)
                        if block_text not in round_yielded_cot:
                            yield {"type": "cot", "data": {"text": block_text}}
                            round_yielded_cot.add(block_text)
                    # 2) 流式版 strip：处理 think 块未关闭的情况
                    new_clean = strip_think_blocks_incremental(round_text_raw)
                    # 计算相对增量（可能为空，例如在 think 块中）
                    if len(new_clean) > len(round_text_clean):
                        out_delta = new_clean[len(round_text_clean):]
                        round_text_clean = new_clean
                        if out_delta:
                            yield {"type": "text", "data": {"delta": out_delta}}
                elif etype == "tool_start":
                    tc = ToolCall(
                        id=event["data"]["id"],
                        name=event["data"]["name"],
                        args=event["data"].get("args") or {},
                    )
                    round_tool_calls.append(tc)
                    # 透传给上层
                    yield event
                elif etype == "error":
                    yield event
                    return
                # 其它事件（来自 LLM 客户端的 end 等）忽略
        except Exception as e:
            logger.exception("Stream LLM call failed, falling back to keyword")
            # LLM 流式失败 → fallback 关键词
            async for ev in _run_keyword_stream(user_text):
                yield ev
            return

        # round 结束：构造 assistant 消息（含 text + tool_use blocks）
        assistant_msg: Message = {"role": "assistant", "content": []}
        if round_text_clean:
            assistant_msg["content"].append(
                {"type": "text", "text": round_text_clean}
            )
        for tc in round_tool_calls:
            assistant_msg["content"].append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.args,
            })
        messages.append(assistant_msg)

        # 如果本轮没调工具，结束（第一版不做流式 markdown fallback，
        # 由非流式 run_chat 处理；流式仅服务 LLM 原生 tool_use 路径）
        if not round_tool_calls:
            break

        # 执行工具（execute_tool 自身 try/except 不会抛异常，但包一层防御）
        tool_result_map: dict[str, str] = {}
        for tc in round_tool_calls:
            logger.info(f"Tool call (stream): {tc.name}({tc.args})")
            try:
                result_str = await execute_tool(tc.name, tc.args)
                ok = True
            except Exception as e:
                logger.exception(f"Tool {tc.name} raised exception")
                result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
                ok = False
            tool_result_map[tc.id] = result_str
            tool_calls_made.append({
                "name": tc.name,
                "args": tc.args,
                "result_preview": result_str[:200],
            })
            yield {
                "type": "tool_end",
                "data": {
                    "id": tc.id,
                    "result": result_str,
                    "ok": ok,
                },
            }

        # 把 tool_results 合并到下一轮 user 消息（Anthropic 风格）
        combined_blocks: list[dict[str, Any]] = []
        for tc in round_tool_calls:
            combined_blocks.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": tool_result_map[tc.id],
            })
        messages.append({"role": "user", "content": combined_blocks})

    # 超过 max_tool_rounds：end 事件由 API 层负责
    return


async def _run_keyword_stream(user_text: str) -> AsyncIterator[StreamEvent]:
    """关键词模式流式（一次性 yield 全部事件，不假装打字机延迟）。

    关键词响应本身就是 < 100ms 的 db 操作，逐字流式没有意义反而
    拖慢体感。所以这里把整段 text 一次性 yield。
    """
    from app.core.chat import dispatch_keyword

    response = await dispatch_keyword(user_text)
    # 关键词响应：单次 text（整段）
    yield {"type": "text", "data": {"delta": response.text}}
    # 无 tool_calls / CoT
    # 不 yield end —— API 层负责


def _iter_new_think_blocks(text: str, start: int) -> list[str]:
    """返回 [start, len(text)) 范围内新增的完整 think 块原文 list。

    完整 think 块 = `<think>...</think>` 形式（_THINK_BLOCK_RE 匹配）。

    ⚠️  此函数**不再使用** —— chat_engine.run_chat_stream 改用
    `round_yielded_cot: set` 跟踪已 yield 块（位置切片会截断跨越
    offset 边界的 think 块，导致捕获失败）。保留仅为向后兼容。
    """
    if not text or start >= len(text):
        return []
    new_part = text[start:]
    return _THINK_BLOCK_RE.findall(new_part)
