# Cockpit — Agent Notes

> 项目级记忆，只在 `cockpit/` 这个项目成立。给后面接手 / 跨时间回看的 agent 用。

## 项目一句话

本地优先的个人项目驾驶舱（FastAPI + Next.js 15），自然语言建项目/任务，完成时沉淀成 achievement 资产。

## 核心路径

- **后端入口**：`app/main.py`，启动 `uvicorn app.main:app --reload --port 7842`
- **前端入口**：`web/`（Next.js App Router），启动 `npm run dev`
- **DB**：`~/.cockpit/cockpit.db`（SQLite）
- **LLM 配置**：DB `settings` 表 key=`llm_config` 优先于 `.env`

## 踩过的坑（已修，但教训值得记）

### 1. TaskRow checkbox 二次确认 UX bug（修于 2026-07-13）

- **症状**：点任务前面的状态圆圈 → 圆圈变对号 → 2 秒后对号变回圆圈 → 任务没完成
- **根因**：`TaskRow` 状态按钮用了双击确认（`confirming` state + 2s `setTimeout` 重置），但**没有视觉提示告诉用户要点第二次**。旁边的 `FocusItem` 是单击直接完成 — 两个区域行为不一致更诡异
- **教训**：重要操作要么"单击 + undo 窗口"（带 toast），要么"显式二次确认按钮"，不要靠"图标变一下就当确认" — 用户根本看不懂
- **修法位置**：`web/components/MainBoard.tsx` TaskRow（约 314 行起）

### 2. LLM CoT 暴露 + markdown fallback 误执行风险（修于 2026-07-13）

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

## 易踩但还没炸的隐患

### `add_task` 幂等检查被 LLM 依赖

`tools.py` 里 `add_task` 做了同项目+同名的幂等检查（返回 existing），但 system prompt 写"不要依赖这个防线"。如果 LLM 看到同名项目/任务时没先 `list_projects` / `list_tasks` 就直接 `add_task`，会触发幂等但**产生静默去重** — 用户的预期可能是"在已有项目下加新任务"而不是"加了个和已有同名的任务"。后端工具层面没问题，前端 prompt 工程是关键。

### `delete_project` 不可逆 + 已有二次确认

`chat_engine.py` 的 system prompt 里写了二次确认流程（要先 list 找到 id → 问用户 → 等明确确认 → 才调 delete_project）。**不要去掉这个确认** — 删项目会清空其下所有任务，不可逆。

## LLM 后端约定

5 个后端（anthropic / deepseek / minimax / openai / custom），deepseek / minimax / openai / custom 都走 `OpenAIClient`（`app/llm/openai.py`）。**这意味着**：

- DeepSeek R1 / MiniMax M3 的 CoT 走 `choice.message.content` 字段（不是 `reasoning_content`），必须 strip
- 不同模型的 tool calling 兼容性差异大，遇到 fallback 路径问题时优先看 `OpenAIClient` 的 tool schema 转换

## 测试

- 后端：`pytest app/tests/ -v`（66 tests）
- 前端类型：`cd web && npx tsc --noEmit`
- 改 Python 前必须 `rm -rf app/llm/__pycache__` 否则 uvicorn `--reload` 不生效
