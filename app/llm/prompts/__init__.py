"""Cockpit system prompt 加载器 (2026-07-22 抽)。

背景: 原本 SYSTEM_PROMPT 是 235 行三引号字符串, 跟 Python 代码挤在
app/llm/chat_engine.py 里。改 prompt 需要碰 .py、触发 Python reload、
改坏了好排查。

重构: 抽到 app/llm/prompts/cockpit_system.md 纯文本, Python 启动时
read_text() 加载。改 prompt:
- 不用碰 .py 代码
- 不用触发 Python reload
- 改坏能直接 diff 看
- 非工程师能改 prompt

设计:
- 模块顶层加载一次 (eager load), 后续直接用 module-level 常量
- 加载失败 fail fast: FileNotFoundError 直接报 (比静默回退到旧 prompt 强)
- 保留 SYSTEM_PROMPT 这个名字作为 module-level 常量, 让 chat_engine.py
  的 import 几乎不动 (只改 import 路径)
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent
_SYSTEM_PROMPT_PATH = _PROMPTS_DIR / "cockpit_system.md"


def load_system_prompt(path: Path = _SYSTEM_PROMPT_PATH) -> str:
    """从 .md 文件加载 system prompt。

    Args:
        path: prompt 文件路径, 默认 app/llm/prompts/cockpit_system.md

    Returns:
        prompt 文本 (strip 尾部空白, 跟原本三引号字符串行为一致)

    Raises:
        FileNotFoundError: 文件不存在 — fail fast, 不静默回退
    """
    return path.read_text(encoding="utf-8").rstrip()


# 模块加载时 eager load — chat_engine.py 后续 `from app.llm.prompts import SYSTEM_PROMPT` 直接拿到
SYSTEM_PROMPT: str = load_system_prompt()


__all__ = ["SYSTEM_PROMPT", "load_system_prompt"]
