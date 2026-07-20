"""ChatWindow 重构不变量测试 (2026-07-20 立)。

背景:
- ChatWindow 重构把 SSE 流式状态机从 869 行的 ChatWindow 抽到 web/lib/hooks/useChatStream.ts
- 重构后 ChatWindow 776 行, 流式状态机 150 行独立可测
- 锁住: ChatWindow 不应该再"自己实现"流式 (即不应该再调 api.chatStream)

不变量:
1. ChatWindow 必须 import useChatStream
2. ChatWindow 不能直接调 api.chatStream（流式状态机已抽到 hook）
3. ChatWindow 不能有 setMessages 调用 (state 归 hook 管)
4. useChatStream hook 必须存在
5. useChatStream hook 必须 export send / setHistory / clear
"""
import re
from pathlib import Path

WEB_DIR = Path(__file__).parent.parent.parent / "web"
CHATWINDOW_TSX = WEB_DIR / "components" / "ChatWindow.tsx"
HOOK_FILE = WEB_DIR / "lib" / "hooks" / "useChatStream.ts"


def test_use_chat_stream_hook_exists():
    """useChatStream hook 文件必须存在（2026-07-20 立）。"""
    assert HOOK_FILE.exists(), (
        f"{HOOK_FILE} 不存在 — useChatStream hook 是这次重构的核心交付物, "
        "缺失 = 869 行 ChatWindow 又回来了"
    )


def test_chatwindow_uses_hook():
    """ChatWindow 必须 import useChatStream。"""
    src = CHATWINDOW_TSX.read_text(encoding="utf-8")
    assert "useChatStream" in src, (
        "ChatWindow 没有 import useChatStream — 流式状态机可能还在 ChatWindow 里"
    )
    # 必须真的调用 hook (useChatStream({...}))
    assert "useChatStream({" in src, (
        "ChatWindow 没调 useChatStream() — 导入但未使用 = 死代码"
    )


def test_chatwindow_no_direct_chatstream_call():
    """ChatWindow 不应再直接调 api.chatStream（重构后归 hook 管）。"""
    src = CHATWINDOW_TSX.read_text(encoding="utf-8")
    # 排除 hook 自身 (hooks/useChatStream.ts 调 api.chatStream 是对的)
    assert "api.chatStream(" not in src, (
        "ChatWindow 直接调 api.chatStream — 重构没生效, "
        "流式状态机应该只在 useChatStream hook 里"
    )


def test_chatwindow_no_setmessages():
    """ChatWindow 不应再有 setMessages 调用（state 归 hook 管）。"""
    src = CHATWINDOW_TSX.read_text(encoding="utf-8")
    # setHistory 是 hook 提供的 setter, 是 OK 的
    # setMessages 才是问题
    assert "setMessages(" not in src, (
        "ChatWindow 还有 setMessages() 调用 — state 应归 useChatStream hook 管, "
        "UI 组件不应该直接操作 messages state"
    )


def test_hook_exports_required_api():
    """useChatStream hook 必须 export send / setHistory / clear。"""
    src = HOOK_FILE.read_text(encoding="utf-8")
    for fn in ["send", "setHistory", "clear"]:
        # 函数定义或返回字段
        assert f"const {fn}" in src or f"{fn}:" in src, (
            f"useChatStream hook 缺 {fn} — ChatWindow 会拿不到这个能力"
        )


def test_hook_returns_messages_loading():
    """useChatStream hook 必须返回 messages / loading 状态。"""
    src = HOOK_FILE.read_text(encoding="utf-8")
    # 找最后的 return { ... } 块
    # 不用 regex (函数体里还有别的 {}), 改用最后一行匹配
    lines = [l for l in src.split("\n") if l.strip().startswith("return ")]
    assert lines, "useChatStream hook 缺 return 语句"
    last_return = lines[-1]
    assert "messages" in last_return, f"hook 末次 return 缺 messages, got: {last_return!r}"
    assert "loading" in last_return, f"hook 末次 return 缺 loading, got: {last_return!r}"
