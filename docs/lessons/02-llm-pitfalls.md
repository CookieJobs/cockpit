# 02 — LLM 集成 Lessons

> 跟 LLM 调用相关的坑。CoT 暴露 / markdown fallback 误执行是 P0 级 — 涉及数据安全。

## #2. LLM CoT 暴露 + markdown fallback 误执行风险（修于 2026-07-13）

- **症状**：DeepSeek R1 / MiniMax M3 等推理模型在 content 字段写 `<think>...</think>`，整条管道没过滤直接渲染给用户；更严重的是 `chat_engine.py` 的 markdown tool call fallback 用正则扫 `response.text` 解析 `functions.xxx(args)` 伪调用 — 如果 LLM 在 CoT 思维里写了 `functions.delete_task(...)`，**会被当真工具调用执行**（潜在不可逆数据丢失）
- **根因**：chat_engine 没处理 CoT 块，前后端 markdown 渲染都不过滤
- **教训**：
  - **后端**必须在 LLM 响应**入口**就剥离 CoT（`strip_think_blocks` 在 `chat_engine.py`），不能让任何下游路径（fallback 解析 / 持久化 / 前端显示）拿到带 CoT 的 text
  - **前端**再做一次 defense-in-depth（处理旧 session 历史里残留的 CoT）
  - markdown tool call fallback **永远是正则 + 白名单**，必须假设输入里可能有 CoT / 注释 / 乱码
- **覆盖范围**：匹配 `<think>` / `<thinking>` / `<reasoning>` 三个变体，case-insensitive，容忍空白
- **修法位置**：
  - 后端：`app/llm/chat_engine.py`（`_THINK_BLOCK_RE` + `strip_think_blocks`）
  - 前端：`web/components/ChatWindow.tsx`（`stripThinkBlocks` 在 `extractTextFromAnthropicContent` 之后）

---

> **未来可能加的 lessons**（暂记这里防忘）：
> - 多 LLM 后端切换的 tool schema 兼容（OpenAIClient 共享）— 如果切到某后端 tool 调不通
> - streaming chunk 顺序错乱（DeepSeek 偶发）的重试策略
