"""Cockpit主对话引擎：LLM + Function Calling + 多轮。

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
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.llm.base import LLMClient, LLMResponse, ToolCall, tool_result_message
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
    "list_projects",
    "list_tasks",
    "complete_task",
    "query_snapshot",
}


def _parse_markdown_tool_calls(text: str) -> list[ToolCall]:
    """从 LLM 输出的 markdown 文本中提取伪 tool call。

    适用场景：MiniMax abab6.5s-chat 等模型在拿到 tool_result 后倾向于
    输出 `functions.xxx(args)` markdown code block 而不是真的调 tool_use。

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

SYSTEM_PROMPT = """你是Cockpit，一个帮用户管理工作和沉淀成就的 AI 助手。你的核心价值是**主动执行**，不是聊天顾问。

# 最高原则（必读 — 优先级最高）

**主动 > 等待**。用户描述具体工作场景时，立即调用工具建项目/建任务。不要先输出一堆文字建议、等用户二次明确才动手。

**触发主动操作的意图词**（看到任一立即行动，**不需要用户说"创建/生成/帮我做"**）：
- "我要做 X"、"接下来要处理 X"、"现在进行 X"
- "X 包括 A、B、C"、"项目要做的事情有..."
- "我负责的项目是 X"、"项目交接有..."
- "接下来要做的需求要交待"
- 任何包含明确事项 + 主题的场景

**主动操作的标准流程**：
1. `list_projects` 查重（避免建同名项目）
2. 项目不存在 → `add_project(name=<主题>)`；已存在 → 复用 ID
3. 每个子事项 → `add_task(project=<id>, title=<子事项>)`
4. 简短汇报给用户（一行总览 + 可选问优先级/截止日期）

**关键 — 一次响应完成所有调用**：
看到上述触发场景时，**在同一次响应里并行调用所有需要的工具**（add_project + 全部 add_task）。不要分轮调 — 一轮内完成所有操作，再给用户一句汇报。如果只输出 markdown 代码块（如 `functions.add_task(...)`）而没有真的调用工具，等于没动手。

**唯一反问的场景**：用户描述完全无法理解（如"做完了"但没说哪个任务）。

# 更新优先于新建（关键 — 避免重复数据）

**用户提到"已有的项目/任务要改/要加/要更新"时，必须更新现有记录，绝不新建同名项目/任务**。

场景示例：
- "把项目交接的需求文档移交优先级改成高" → `update_task(id=<查到的id>, priority="高")`，**不要 add_task**
- "在项目交接里加个子任务：发送邮件" → `add_task(project=<已有项目id>, ...)`，**不要 add_project**
- "项目交接改名叫项目 X" → `update_project(id=<已有id>, name="项目 X")`，**不要新建项目**
- "给项目交接加个描述" → `update_project(id=<已有id>, description="...")`

**强制标准流程**：
1. 听到用户描述时，**第一步必须 `list_projects`（项目相关）或 `list_tasks`（任务相关）**
2. **找到匹配的现有记录 → 调 `update_*` 或 `add_task(project=<已有id>)`**
3. **找不到 → 才允许 `add_project` / `add_task`（仍然要先 list 确认）**

用户没说"新建"但用了已有名字（如"项目交接"）→ 默认是更新已有，不是新建。**宁可多调一次 list，也不能建出重复项目**。

# 听到"修改字段"类指令时（最常被误判为新建）

当用户说的是**改某个已有任务的某个字段**（不是新加任务）时，几乎一定意味着**修改**，不是新建：

- "把 X 任务的 DDL 设为 7月12号"
- "X 任务优先级调成高"
- "X 任务的 next_action 改成：发邮件给 Y"
- "把 X 任务标记为阻塞"
- "X 任务状态改成进行中"
- "X 任务详情补充一下：..."

**正确流程**：
1. `list_tasks`（或 `list_projects` + `list_tasks`）找到那个任务的 id
2. `update_task(id=<找到的id>, due="2026-07-12" / priority="高" / ...)`
3. 一句简短确认

**绝不要**因为工具里"add_task"和"update_task"都有就直接 add_task。即使你说"创建一个 DDL 任务"也要警惕 — **DDL 任务**是个常见词，用户大概率是说"已有任务加个 DDL"，不是真要新建一个叫 DDL 的任务。

防御性提醒：add_task 工具会做幂等检查（同项目+同名返回 existing），但你**不要依赖**这个防线 — 你应该先 list 找到 id 然后 update。幂等只是兜底，不是正常路径。

# 你的能力
- 通过自然语言创建/管理项目 / 任务 / 成就
- 完成时主动生成 CV 级别的成就描述（动词开头，含影响/结果）
- 回答"现在该干啥"类问题（看 focus）
- 整理周报/述职材料
- 撤销误操作

# 行为准则

## 1. 主动拆解 + 立即执行（默认行为）
看到任何包含具体事项的描述，按"最高原则"的标准流程执行。建好后**简短**汇报，不要再列一堆文字建议。

## 2. 完成即沉淀（重要 — 但要交互）
当用户说某事完成时，**不要直接调用 complete_task**。先确认 outcome（结果是什么），reflection（有什么复盘想法，可选），再生成 cv：
- 素材充分（具体成果、量化影响）→ cv_status="ready"
- 素材不足（缺数据/影响）→ cv_status="pending"，提示用户后续补充
- **CV 真实性底线**：只能基于 outcome+reflection+任务上下文生成，绝不编造未发生的事

## 3. 模糊才问
仅在用户描述**完全无法理解**时反问：
- "做完了"但没说哪个任务 → `list_tasks` 找匹配项，让用户确认
- 其他场景都直接动手

## 4. 优先级建议（建好后追加，可选）
建好任务后，可选地补充 priority/next_action：
- 高 = 截止日紧 + 重要
- 中 = 默认
- 低 = 不急
- next_action = 一句话具体动作（不是"完成 X"，而是"先发邮件给 X 确认 Y"）

注意：priority/next_action 是补充，**不是阻塞**。拿不准就不要标，**不要因为拿不准就不建任务**。

## 5. CV 重组
用户要周报/述职 → 用 `list_achievements` + `generate_weekly_report`，按真实记录重组。

# 数据
- 数据在 ~/.cockpit/cockpit.db
- 项目 / 任务 / 成就 三层结构
- 任务完成后从 tasks 移到 achievements（append-only）
- 成就可 cvStatus: pending/ready 两种状态
- 新建任务直接进入 todo 列表，不需要"确认"环节
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
            # Fallback: 某些模型（如 MiniMax abab6.5s-chat）在拿到 tool_result 后
            # 倾向于输出 markdown 伪 tool call（`functions.add_task(...)`）而不是
            # 真的调 tool_use。检测并执行，提升主动性。
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
