"""Markdown 渲染升级不变量测试 (2026-07-22 立)。

背景:
- 之前 web/components/Markdown.tsx 是手写极简解析器 (v1.0), 只支持 # 标题 /
  无序列表 / **bold** / `code`, LLM 常用的有序列表 / 任务清单 / 引用 / 表格 /
  多行代码块 / 链接 / 分割线全不识别 → Agent 拆任务时的 "1. **xxx**" 退化成
  裸文本段落, 视觉很丑
- 2026-07-22 升级到 react-markdown + remark-gfm (GFM) + rehype-highlight
- 流式渲染策略: 用户拍板"流式期也跑 markdown" (跟旧版"流式期纯文本 + 光标"
  不同, 接受增量解析可能的小闪烁)

锁住的不变量 (6 条):
1. Markdown.tsx 必须 import + 实际使用 react-markdown (不能回退到手写解析)
2. Markdown.tsx 必须配 remark-gfm (GFM 语法支持, 用户痛点: 任务清单 / 表格)
3. Markdown.tsx 必须配 rehype-highlight (代码块语法高亮)
4. MarkdownView 组件必须有 markdown className (沿用 globals.css 的 prose 样式)
5. ChatWindow 必须 import MarkdownView (不能直接调手写 renderMarkdown)
6. EventsView 流式期最后 text 段必须走 MarkdownView (用户 2026-07-22 拍板
   "流式期也跑 markdown", 不能再回退到纯文本 + 光标)
"""
import re
from pathlib import Path

# 源码路径 — 跟着项目根走, 不依赖 cwd
WEB_DIR = Path(__file__).parent.parent.parent / "web"
MARKDOWN_TSX = WEB_DIR / "components" / "Markdown.tsx"
CHATWINDOW_TSX = WEB_DIR / "components" / "ChatWindow.tsx"


def test_markdown_uses_react_markdown():
    """Markdown.tsx 必须 import + 实际使用 react-markdown (不能回退手写)。"""
    src = MARKDOWN_TSX.read_text(encoding="utf-8")
    assert "react-markdown" in src, (
        "Markdown.tsx 没 import react-markdown — LLM 常用的有序列表 / 任务清单 / "
        "引用 / 表格 / 多行代码块 / 链接 / 分割线全退化, 回退到 2026-07-22 之前"
        "的手写解析器状态"
    )
    # 必须真的用, 不只是 import (import 但不用 = 死代码 = 退回到手写)
    assert "ReactMarkdown" in src or "<ReactMarkdown" in src, (
        "Markdown.tsx import 了 react-markdown 但没用 — 死代码, 实际渲染走"
        "别路径 (可能回退到老的 v1.0 解析器)"
    )


def test_markdown_remark_gfm():
    """Markdown.tsx 必须配 remark-gfm (GFM 语法支持)。"""
    src = MARKDOWN_TSX.read_text(encoding="utf-8")
    assert "remark-gfm" in src, (
        "Markdown.tsx 没配 remark-gfm — GFM 语法 (任务清单 - [x] / 表格 | "
        "| --- | / 删除线 ~~ / autolink) 全不支持, LLM 输出的 GFM 元素退化为"
        "裸文本"
    )
    # 必须真的传 remarkPlugins prop
    assert "remarkPlugins" in src and "remarkGfm" in src, (
        "Markdown.tsx import 了 remark-gfm 但没传给 remarkPlugins prop — "
        "GFM 语法实际不生效, 跟没加一样"
    )


def test_markdown_rehype_highlight():
    """Markdown.tsx 必须配 rehype-highlight (代码块语法高亮)。"""
    src = MARKDOWN_TSX.read_text(encoding="utf-8")
    assert "rehype-highlight" in src, (
        "Markdown.tsx 没配 rehype-highlight — 代码块无语法高亮, 退化为纯黑"
        "底色 + 纯白文字, 跟 dark theme 视觉割裂"
    )
    assert "rehypePlugins" in src and "rehypeHighlight" in src, (
        "Markdown.tsx import 了 rehype-highlight 但没传给 rehypePlugins prop — "
        "高亮实际不生效"
    )


def test_markdownview_has_markdown_class():
    """MarkdownView 组件必须挂 markdown className (沿用 globals.css 的 prose 样式)。"""
    src = MARKDOWN_TSX.read_text(encoding="utf-8")
    # 找 MarkdownView 函数体
    fn_match = re.search(
        r'function\s+MarkdownView\s*\([^)]*\)\s*\{',
        src,
    )
    assert fn_match, "MarkdownView 组件函数找不到"
    # 函数体里必须有 markdown className
    body_start = fn_match.end()
    body = src[body_start:body_start + 500]  # 取前 500 字符
    assert 'className="markdown' in body or "className={`markdown" in body, (
        "MarkdownView 组件没挂 markdown className — globals.css 的 .markdown "
        "样式不生效, 标题 / 列表 / 引用 / 表格 / 代码块 全没视觉强调"
    )


def test_chatwindow_uses_markdownview():
    """ChatWindow 必须 import MarkdownView (不能直接调手写 renderMarkdown)。"""
    src = CHATWINDOW_TSX.read_text(encoding="utf-8")
    assert "import { MarkdownView }" in src, (
        "ChatWindow 没 import MarkdownView — 渲染路径可能回退到老的"
        "renderMarkdown 手写函数"
    )
    # 必须真的用, 不只是 import
    assert "<MarkdownView" in src, (
        "ChatWindow import 了 MarkdownView 但没实际使用 — 死代码, 实际渲染"
        "走老路径"
    )
    # 不能直接 import 老的 renderMarkdown (已经删除, 但 import 残留也会报编译错)
    assert "import { renderMarkdown }" not in src, (
        "ChatWindow 还有 import { renderMarkdown } — 老的 v1.0 手写解析器"
        "已删除 (2026-07-22 升级), 残留 import 编译报错"
    )


def test_eventsview_streaming_uses_markdownview():
    """EventsView 流式期最后 text 段必须走 MarkdownView (用户 2026-07-22 拍板
    '流式期也跑 markdown', 不能再回退到纯文本 + 光标)。

    实际写法 (2026-07-22 升级): 所有 text 段都走 MarkdownView (流式非流式一致),
    光标作为独立元素追加在最后 text 段末尾, 用 {streaming && isLastText && <span>}
    JSX 表达式表达。

    锁住:
    1. text 段渲染必须用 MarkdownView (不能是 {e.content} 纯文本输出)
    2. 不能用 whitespace-pre-wrap 渲染 e.content (那是 v1.0 流式期纯文本策略)
    3. 光标必须用 JSX 表达式条件渲染 (streaming && isLastText)
    """
    src = CHATWINDOW_TSX.read_text(encoding="utf-8")
    # 找 EventsView 函数体
    fn_match = re.search(
        r'function\s+EventsView\s*\([^)]*\)\s*\{',
        src,
    )
    assert fn_match, "EventsView 组件函数找不到"
    body_start = fn_match.end()
    body = src[body_start:body_start + 4000]

    # 1. text 段必须用 MarkdownView
    assert "<MarkdownView" in body, (
        "EventsView 没渲染 MarkdownView — text 段没走 markdown, "
        "回退到 v1.0 纯文本输出, 违反 2026-07-22 升级目标"
    )

    # 2. 不能用 whitespace-pre-wrap 容器包 {e.content} (那是 v1.0 流式纯文本)
    # 注: 同文件里 user message (行 474) 和 CotBlock (行 804) 用了 whitespace-pre-wrap,
    # 但不是 EventsView 渲染 e.content 的方式。用反向 pattern 检查更精确:
    bad_pattern = re.search(
        r'whitespace-pre-wrap[^}\n]{0,80}\{e\.content\}',
        body,
    )
    assert not bad_pattern, (
        f"EventsView 用 whitespace-pre-wrap 容器渲染 {{e.content}} — "
        f"v1.0 流式期纯文本策略残留, 违反 '流式期也跑 markdown' 拍板. "
        f"匹配: {bad_pattern.group(0) if bad_pattern else '?'}"
    )

    # 3. 光标必须用 streaming && isLastText 条件渲染
    cursor_match = re.search(
        r'streaming\s*&&\s*isLastText',
        body,
    )
    assert cursor_match, (
        "EventsView 找不到 'streaming && isLastText' 条件渲染光标 — "
        "要么光标位置逻辑改了 (要 review), 要么没加流式期光标 (cursor 永远"
        "显示或永远不显示, 都不对)"
    )
    # 光标必须在 MarkdownView 渲染之后 (顺序渲染, 光标跟在 markdown 后面)
    markdown_pos = body.find("<MarkdownView")
    cursor_pos = body.find("cursor-blink")
    assert markdown_pos != -1 and cursor_pos != -1, (
        "EventsView 找不到 MarkdownView 或 cursor-blink, 代码结构异常"
    )
    assert markdown_pos < cursor_pos, (
        "EventsView 光标位置在 MarkdownView 之前 — 视觉上光标会先出现然后"
        "才是 markdown 内容, 应该 markdown 渲染后追加光标"
    )
