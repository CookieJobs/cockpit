"""P0 regression: chain-of-thought is never an API, persistence, or DOM field."""
from pathlib import Path


CHAT_API = Path(__file__).parent.parent / "api" / "chat.py"
CHAT_WINDOW = Path(__file__).parent.parent.parent / "web" / "components" / "ChatWindow.tsx"
STREAM_HOOK = Path(__file__).parent.parent.parent / "web" / "lib" / "hooks" / "useChatStream.ts"


def test_chat_sse_end_payload_does_not_expose_cot_blocks():
    source = CHAT_API.read_text(encoding="utf-8")
    end_slice = source[source.index('yield _sse_format("end"'):]

    assert '"cot_blocks"' not in end_slice
    assert "cot_blocks: list[str]" not in source


def test_frontend_has_no_cot_toggle_or_rendering_channel():
    window = CHAT_WINDOW.read_text(encoding="utf-8")
    hook = STREAM_HOOK.read_text(encoding="utf-8")

    for forbidden in ["SHOW_COT_STORAGE_KEY", "CotBlock", "showCot", "cotBlocks"]:
        assert forbidden not in window
        assert forbidden not in hook
