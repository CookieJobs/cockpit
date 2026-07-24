"""ChatWindow 输入/响应不变量静态分析测试 (2026-07-20 立)。

背景:
- 用户报两个 chat 体验 bug:
  1. 点击发送后输入框内容不清理, "测试" 还在输入框里
  2. 点击发送后 agent 消息立即显示"（无响应）", 实际流式还没到
- 这俩都是前端 UX bug, 端到端 (E2E) 测不到, 单元测试也难覆盖
  (需要 jsdom + mock fetch + RTL 渲染 ChatWindow 整树, 太重)
- 沿用 task-cockpit 不变量测试方法论: 静态扫源码 + 关键字符串存在性检查,
  编译时保证, 比运行时 E2E 快 100 倍, 不需要浏览器

覆盖的不变量 (2 条):
1. onSubmit 必须在 send 之后清空 input (setInput(""))
2. AgentMessageContent 退化路径必须先判断 streaming, 避免流式期间显示"（无响应）"
"""
from pathlib import Path

CHATWINDOW_TSX = (
    Path(__file__).parent.parent.parent
    / "web"
    / "components"
    / "ChatWindow.tsx"
)


def read_chatwindow() -> str:
    if not CHATWINDOW_TSX.exists():
        raise FileNotFoundError(f"ChatWindow.tsx not found at {CHATWINDOW_TSX}")
    return CHATWINDOW_TSX.read_text(encoding="utf-8")


# ===== 不变量 1: 发送后清空输入框 =====


def test_onsubmit_clears_input_after_send():
    """onSubmit 必须在 send(input) 之后调 setInput(""), 否则用户感觉『重发』。

    历史 bug (2026-07-20): 用户报『点击发送后输入框里测试还在』。
    根因: form onSubmit 只调 send(input), 没清 input state, 视觉上跟『重发』无差。
    修法: send() 之后立即 setInput("")。
    """
    src = read_chatwindow()
    # 找 form onSubmit 的函数体 — 简单粗暴地找 onSubmit 后的 6 行
    # ChatWindow 里只有一个 form onSubmit, 不会误匹配
    idx = src.find("onSubmit={(e) => {")
    assert idx >= 0, "ChatWindow 找不到 form onSubmit, 布局大改需要手动检查"
    # 抓 onSubmit 函数体到下一个 </form> 之间 200 字符够用
    snippet = src[idx : idx + 400]
    # send 必须在 onSubmit 里
    assert "send(" in snippet, "form onSubmit 里没调 send, 消息没发送"
    # setInput("") 必须在 onSubmit 里 (这是修复点)
    assert 'setInput("")' in snippet, (
        'form onSubmit 没调 setInput(""), 发送后输入框内容不清理, '
        "用户感觉『重发』 (历史 bug 2026-07-20)"
    )


def test_onsubmit_guards_empty_trimmed():
    """onSubmit 必须 guard trim 后为空的情况 (如纯空格), 否则 send 误调。

    配套不变量: 修了 #1 后, send(trimmed) + setInput("") 之间如果 trim 后是空,
    send 会被 guard 住 (hook 内部已经 trim 判断), 但 setInput("") 还是会清空
    input — 体验正常。 不过保险起见, 期望 onSubmit 自己再 guard 一次。
    """
    src = read_chatwindow()
    idx = src.find("onSubmit={(e) => {")
    assert idx >= 0, "ChatWindow 找不到 form onSubmit"
    snippet = src[idx : idx + 400]
    # 期望先 trim + guard, 再 send + setInput
    assert "trim()" in snippet, "onSubmit 没 trim input, 前后空格会被当内容发出去"
    assert "if (!trimmed) return" in snippet or "if (!trimmed)" in snippet, (
        "onSubmit 没 guard 空 trim (如纯空格), send hook 内部会 return 但 setInput "
        "还是会清, 体验正常但代码不严谨。建议保留显式 guard 显式表达意图。"
    )


# ===== 不变量 2: streaming 期间不显示"（无响应）" =====


def test_agent_message_content_guards_streaming_in_fallback():
    """AgentMessageContent 退化路径必须先判断 streaming, 流式期间显示"思考中…"。

    历史 bug (2026-07-20): 用户报"刚点击发送, agent 消息立刻显示（无响应）"。
    根因: useChatStream 创建的初始 agent stub 是 events=[] + content=undefined,
    AgentMessageContent 里 hasEvents=false 走退化路径, text fallback 到
    "（无响应）", 跟流式期间的实际状态完全不符。
    修法: 退化路径开头加 `if (message.streaming) return <思考中…>`, 优先级
    高于 content/toolCalls 的 fallback。
    """
    src = read_chatwindow()
    # 找 AgentMessageContent 函数
    idx = src.find("function AgentMessageContent")
    assert idx >= 0, "ChatWindow 找不到 AgentMessageContent 函数, 组件结构大改需手动检查"
    # 抓函数体到下一个 "function " 或 "}" 收尾
    # 简化: 抓到文件末尾都行, 因为整个文件里只有这一处
    body = src[idx:]
    # 退化路径里要看到 message.streaming 判断
    assert "message.streaming" in body, (
        "AgentMessageContent 完全没检查 message.streaming — 流式期间 (events=[] + "
        "content=undefined) 一定会显示『（无响应）』闪烁 (历史 bug 2026-07-20)"
    )
    # 退化路径里的 streaming 分支要返回"思考中" 而不是"（无响应）"
    # 找 "（无响应）" 字面量位置
    fallback_idx = body.find("（无响应）")
    assert fallback_idx > 0, 'AgentMessageContent 退化路径里没找到 "（无响应）" 字面量'
    # streaming 判断必须在 fallback 之前
    streaming_idx = body.find("message.streaming")
    assert streaming_idx > 0 and streaming_idx < fallback_idx, (
        f"AgentMessageContent 退化路径里 message.streaming ({streaming_idx}) "
        f"必须在『（无响应）』({fallback_idx}) 之前出现, 否则 streaming 期间还是会 "
        "显示『（无响应）』 (历史 bug 2026-07-20)"
    )


def test_events_view_uses_thinking_text_during_streaming():
    """EventsView 空 events 时: streaming=true 显示"思考中…", 不是"（无响应）"。

    EventsView 是新流式消息的主渲染路径, 空 events 时也必须按 streaming 区分
    状态。这条历史是 OK 的 (2026-07-20 验过), 但作为防退化测试保留。
    """
    src = read_chatwindow()
    idx = src.find("function EventsView")
    assert idx >= 0, "ChatWindow 找不到 EventsView 函数, 组件结构大改需手动检查"
    body = src[idx : idx + 1500]  # EventsView 函数体有限
    # 期望: 看到 `streaming ? "思考中…" : "（无响应）"` 三元
    assert 'streaming ? "思考中' in body, (
        'EventsView 空 events 时没有按 streaming 区分状态 — 流式期间会显示'
        '『（无响应）』 (历史 bug 2026-07-20)'
    )
    assert "（无响应）" in body, (
        'EventsView 缺"（无响应）" fallback — 历史/错误消息没文字显示。 '
        "注意: 这条只是确认 fallback 文案存在, 不锁住顺序"
    )


# ===== 不变量 3: 不能有顶层 loading 框 (跟 streaming 消息气泡重复) =====


def test_no_top_level_loading_thinking_indicator():
    """ChatWindow 不能在 messages.map 之后另起一个 `{loading && <思考中...>}` 块。

    历史 bug (2026-07-23): 用户报"发完消息后红框区域有 2 个思考中" — 顶部一个
    + 消息气泡内 EventsView 一个, 视觉堆叠。
    根因: useChatStream 里 setMessages 之后立即 setLoading(true), 所以
    `loading=true` 跟 "messages 里有 streaming agent message" 永远同时为真。
    ChatWindow 又同时在两个地方渲染"思考中", 必然重复。
    修法: 删掉顶层那个 `{loading && (...)}` 块, 只保留消息气泡内的 EventsView
    "思考中..." (这条更精准, 因为它就是 stub message 的视觉表达)。
    """
    src = read_chatwindow()
    # 找 messages.map 之后、 输入区之前那一片区域
    # 简化: 找 "messages.map" 在源码里的最后出现 (新流式就是这里), 然后扫到下一个 "</form>" 或 "border-t border-border p-3" (输入区)
    last_map_idx = src.rfind("messages.map")
    assert last_map_idx > 0, "ChatWindow 找不到 messages.map, 组件结构大改需手动检查"
    # 输入区标记: <form 或 border-t border-border p-3
    input_marker = src.find("border-t border-border p-3", last_map_idx)
    assert input_marker > 0, "ChatWindow 找不到输入区 marker, 组件结构大改需手动检查"
    # 中间这片区就是 "messages 之后 到 输入区之前"
    between = src[last_map_idx:input_marker]
    # 不能有顶层 `{loading && (` 块
    assert "{loading && (" not in between, (
        "ChatWindow 在 messages.map 之后另起了一个 {loading && (...)} '思考中...' "
        "块 — 这跟消息气泡内 EventsView 的 '思考中…' 必然重复 (历史 bug 2026-07-23), "
        "用户视觉上看到 2 个堆叠的 loading 框。删掉顶层这个, 只保留消息气泡内的。"
    )
    # 也不能有 fade-in + 思考中 这种模式
    assert "思考中" not in between, (
        "ChatWindow 在 messages.map 之后到输入区之间出现了 '思考中' 文案 — "
        "可能是顶层 loading 框, 跟消息气泡内的 streaming '思考中…' 重复 (历史 bug 2026-07-23)"
    )


def test_thinking_text_appears_only_inside_message_bubble():
    """「思考中」只允许出现在 AgentMessageContent 退化路径 + EventsView 内部。

    跟 test_no_top_level_loading_thinking_indicator 互补: 锁住「思考中」只
    在两个允许的位置出现, 不在其他地方冒出来 (比如顶层、提示条、footer)。
    """
    src = read_chatwindow()
    # 找出所有 "思考中" 出现的位置
    import re
    positions = [m.start() for m in re.finditer("思考中", src)]
    assert len(positions) >= 1, "ChatWindow 完全找不到『思考中』, 流式期间没视觉信号"
    # 每个位置都得在 AgentMessageContent 或 EventsView 函数体内
    agent_content_idx = src.find("function AgentMessageContent")
    events_view_idx = src.find("function EventsView")
    assert agent_content_idx > 0 and events_view_idx > 0, (
        "ChatWindow 找不到 AgentMessageContent / EventsView, 组件结构大改需手动检查"
    )
    for pos in positions:
        in_agent = agent_content_idx <= pos < events_view_idx
        in_events = events_view_idx <= pos
        assert in_agent or in_events, (
            f"ChatWindow 在位置 {pos} 出现『思考中』, 但不在 AgentMessageContent "
            f"({agent_content_idx}) 或 EventsView ({events_view_idx}) 函数体内 — "
            "可能导致视觉堆叠 (跟消息气泡内的『思考中…』重复, 历史 bug 2026-07-23)"
        )
