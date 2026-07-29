"""完成任务 toast 庆祝不变量 (2026-07-28 立, D 项)。

改造 (D 项):
- 弹窗关闭后弹一个轻量 toast, 告诉用户"已沉淀 · 累计 N 个 ready"
- 跳转到 /achievements 的入口 (让"完成即沉淀"的价值用户当下能看见)
- 任何走 CompleteTaskModal 的入口 (MainBoard + /today) 都必须弹 toast

这条测试锁住, 防退化。
"""
import re
from pathlib import Path

# 源码路径 — 跟着项目根走
MAINBOARD_TSX = (
    Path(__file__).parent.parent.parent / "web" / "components" / "MainBoard.tsx"
)
TODAY_PAGE_TSX = (
    Path(__file__).parent.parent.parent / "web" / "app" / "today" / "page.tsx"
)
TOAST_TSX = (
    Path(__file__).parent.parent.parent / "web" / "components" / "Toast.tsx"
)
LAYOUT_TSX = (
    Path(__file__).parent.parent.parent / "web" / "app" / "layout.tsx"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ===== Toast 组件本身 =====


def test_toast_component_exists():
    """Toast 组件必须存在 (作为公共组件供各页面使用)。"""
    src = read(TOAST_TSX)
    assert "export function ToastProvider" in src, "ToastProvider 必须导出"
    assert "export function useToast" in src, "useToast hook 必须导出"
    assert "export interface ToastItem" in src, "ToastItem 类型必须导出"


def test_toast_provider_mounted_in_root_layout():
    """ToastProvider 必须在根 layout 包 children, 全局可用。"""
    src = read(LAYOUT_TSX)
    assert "ToastProvider" in src, "layout.tsx 必须 import + 用 ToastProvider"
    assert "<ToastProvider>" in src, "ToastProvider 必须包裹 children"


def test_toast_has_achievement_count_message_in_mainboard():
    """MainBoard 完成入口必须弹 toast, 文案带成就数 + 跳转链接。"""
    src = read(MAINBOARD_TSX)
    # 1. 调 toast.success
    assert "toast.success" in src, "MainBoard 完成路径必须调 toast.success 庆祝"
    # 2. 文案必须包含成就数
    assert "achievementsReady" in src, "toast 文案必须带 achievementsReady 计数 (让用户看见累计)"
    # 3. 必须有跳转 action
    assert "router.push(\"/achievements\")" in src, "toast 必须有跳转到 /achievements 的 action"


def test_toast_has_achievement_count_message_in_today_page():
    """今天页面完成入口也必须弹 toast (跟 MainBoard 一致, 防止只有一处)。"""
    src = read(TODAY_PAGE_TSX)
    assert "toast.success" in src, "/today 完成路径也必须调 toast.success"
    assert "achievementsReady" in src, "/today toast 也必须带成就数"
    assert "router.push(\"/achievements\")" in src, "/today toast 也必须有跳转 action"


# ===== Toast 行为 =====


def test_toast_auto_dismiss_after_timeout():
    """toast 必须有自动关闭机制 (默认 3.5s), 不能永久占据屏幕。"""
    src = read(TOAST_TSX)
    # 必须有 setTimeout dismiss
    assert "setTimeout" in src, "toast 必须有自动关闭定时器"
    # 默认 3500ms
    assert "3500" in src, "toast 默认持续时间 3500ms (3.5 秒)"


def test_toast_pauses_on_hover():
    """hover 时必须暂停自动关闭, 让用户有时间点跳转链接。"""
    src = read(TOAST_TSX)
    assert "onMouseEnter" in src, "toast 必须有 onMouseEnter 暂停"
    assert "onMouseLeave" in src, "toast 必须有 onMouseLeave 恢复"
    assert "setPaused" in src, "toast 必须有 paused 状态"


def test_toast_max_concurrent_limit():
    """toast 必须有最大并发数限制 (避免一次弹 100 个把屏幕撑爆)。"""
    src = read(TOAST_TSX)
    assert "TOAST_LIMIT" in src, "toast 必须有并发上限常量"


# ===== 双向对称性: 完成入口的 toast 文案必须一致 =====


def test_toast_message_text_consistent_across_entry_points():
    """MainBoard 和 /today 的完成 toast 文案必须一致 (UX 一致性)。"""
    mb_src = read(MAINBOARD_TSX)
    today_src = read(TODAY_PAGE_TSX)
    # 找 toast.success 的完整消息字符串 (在反引号 template literal 里)
    mb_match = re.search(r"toast\.success\(\s*`([^`]+)`", mb_src)
    today_match = re.search(r"toast\.success\(\s*`([^`]+)`", today_src)
    assert mb_match, "MainBoard toast.success 文案缺失"
    assert today_match, "/today toast.success 文案缺失"
    # 必须用同一句模板 (除 placeholder 外), 这里只校验都含 🎉 和 ready
    assert "🎉" in mb_match.group(1) and "ready" in mb_match.group(1)
    assert "🎉" in today_match.group(1) and "ready" in today_match.group(1)
    # 文案主体应该一致 (剥掉动态插值的纯文本部分)
    mb_clean = re.sub(r"\$\{[^}]+\}", "X", mb_match.group(1))
    today_clean = re.sub(r"\$\{[^}]+\}", "X", today_match.group(1))
    assert mb_clean == today_clean, (
        f"完成 toast 文案 MainBoard 和 /today 不一致:\n"
        f"  MainBoard: {mb_match.group(1)!r}\n"
        f"  /today:    {today_match.group(1)!r}"
    )
