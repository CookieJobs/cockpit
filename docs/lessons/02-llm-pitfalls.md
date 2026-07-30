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

## 强化：polish_cv 端点也需要剥 CoT（2026-07-30 立，user-reported）

- **症状**：用户报"完成弹窗里润色按钮不可点击 + 追问功能看不出效果"。**根因实际是**：
  1. 润色按钮在 outcome 空时 disabled（设计预期），但**没提示告诉用户为什么灰** → 按钮看起来"无反应"
  2. 后端 LLM 返了 `<think>...</think>{"cv": "X", "follow_up_questions": []}` —— CoT 污染 cv + `follow_up_questions` **永远是 `[]`**，因为 `_parse_llm_json_output` 没剥 CoT 就尝试解析 JSON
  3. 前端 followUpQuestions.length === 0 → 追问卡片不渲染 → "看不出效果"
- **实测后端返的污染**：
  ```
  cv: "<think>The user gave a task title \"完成 PRD\" and result description \"做完了\"..."  ← 含 CoT!
  follow_up_questions: []  ← 永远是空数组
  ```
  用户看到的 cv 框是带 <think> 的乱码，问追问永远不出来。
- **lesson #2 的盲点**：
  - 旧版 #2 只在 `chat_engine.py` 入口剥了 CoT（针对对话场景）
  - **`app/api/llm.py` 的 polish_cv 端点是另一条独立路径**，没走 chat_engine，自然没剥 CoT
  - lesson 学到的不只是"入口要剥 CoT"，而是"**任何 LLM 输出入口都要剥**"——每个新端点都是新风险
- **修法**（3 件事）：
  1. **prompt 强化**——`POLISH_CV_SYSTEM` 加【严格禁止】任何 CoT/解释/markdown 包装，"第一个字符必须是 {，最后一个字符必须是 }"。纯语言层预防
  2. **解析器鲁棒性升级**——`_parse_llm_json_output` 加 5 路径处理（严格 JSON / ```json / ``剥离 / 平衡大括号 JSON 块提取 / 全失败兜底）。**关键**：`<think>...</think>` 必须用正则 + 平衡匹配（`re.DOTALL`）剥掉，再尝试 JSON 解析
  3. **老路径也剥 CoT**——当 `_parse_llm_json_output` 返 `(None, [])` 走老路径（整段当 cv）时，**也要先剥 CoT**。否则 M3 返 "只含 <think> 没 JSON" 时，老路径把含 CoT 整段当 cv → cv 污染
  4. **润色按钮 disabled 提示**——前端 outcome 空时挂"👈 先填结果描述" 小灰字 + 按钮 title 动态化 + cv placeholder 引导
- **教训升级**：
  - **"LLM 入口剥 CoT" 不能是 chat_engine 一处的局部动作**，是**架构级 invariant**：每加一个 LLM 端点，**默认行为就要剥 CoT**，写测试锁住
  - **M3 / DeepSeek R1 等 reasoning model 行为差异**：
    - M3: 默认会写 `` + 解释 + JSON（自然语言偏多）
    - DeepSeek R1: 同样会写 CoT，但 CoT 内部更"推理链条"
    - Anthropic Claude: 默认不写 CoT（除非显式要求）
  - **每加一个端点都要端到端实测一次**——mock 测试通过 ≠ 真实 LLM 行为通过。`get_verified_client` 走 mock 测的全过，但真实 M3 行为 mock 测不出来。**修法**: 端点上线前必跑一次真实 LLM curl，断言响应结构
  - **"按钮 disabled" 不只是 UX 问题，是 diagnostic gap**——用户看不到原因 = 用户不会反馈根因。"按钮没反应" 的报告可能藏着 N 层问题。这次用户只看到按钮 disabled，但根因在 LLM CoT 污染。**所有 disabled 状态都要给可发现性提示**（不只是改 UX 还要让人能定位）
- **端点测试**：`app/tests/test_api_polish_cv.py` 加 5 条新测试
  - `test_polish_cv_strips_think_block_and_parses_json`：M3 真实格式 `` + JSON → 剥 CoT + 透传 questions
  - `test_polish_cv_think_block_with_natural_language_prefix`：自然语言 + `` + JSON → 全部清洗
  - `test_polish_cv_realistic_m3_response_with_think_block`：复刻用户实际看到的格式
  - `test_polish_cv_natural_language_only_no_json_legacy_path`：纯文本老路径
  - `test_polish_cv_think_block_with_no_json_falls_back_to_legacy`：只 `` 没 JSON → 老路径**也要剥 CoT**
- **前端不变量**：`app/tests/test_complete_modal_minimal_invariants.py` 加 1 条
  - `test_modal_polish_button_has_outcome_required_discoverability`：锁住 disabled 提示 + title 动态化 + placeholder 引导
- **修法位置**：
  - 后端：`app/api/llm.py` `POLISH_CV_SYSTEM` (prompt 强化) + `_parse_llm_json_output` (5 路径解析) + `_find_balanced_json` (平衡大括号 helper) + 主函数 (老路径也剥 CoT)
  - 前端：`web/components/CompleteTaskModal.tsx` cv 区域加 outcome 空时提示 + title 动态化 + placeholder 动态化

---

> **未来可能加的 lessons**（暂记这里防忘）：
> - 多 LLM 后端切换的 tool schema 兼容（OpenAIClient 共享）— 如果切到某后端 tool 调不通
> - streaming chunk 顺序错乱（DeepSeek 偶发）的重试策略
