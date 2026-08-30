"""主题/视觉系统不变量静态分析测试 (2026-08-01 立, 2026-08-23 v2 改写)。

v2 改动 (cockpit v2 视觉重设计):
  - 取消 light 模式, 单 dark 主题
  - accent 改霓虹绿 #00ff88 (从 indigo)
  - 玻璃拟态 (.glass / .glass-strong / .glow-accent*)
  - 早期脚本永远加 .dark, 不再读 localStorage 切 light

保留的不变量 (v1 立的, v2 仍要锁):
  - tailwind config 函数形式 color 映射 (lesson #27 防字符串解析)
  - :root 块 CSS variables (>= 12 个 color token)
  - body bg/fg 用 var() 引用
  - tailwind safelist 保留 (P0/P2 badge alpha 变体)
  - lib/theme-core.ts 工具函数齐 + lib/theme.ts re-export
  - 端到端 mjs 跑真实行为

v2 新增不变量:
  - 早期脚本必须加 .dark class (v2 单 dark 入口)
  - ThemeToggle 是只读指示器, 不再是 onClick 按钮
  - globals.css 没有 .dark 块 (v2 单主题不需要)
  - tailwind config 有 backdropBlur / boxShadow.glow* / perspective 预设
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

# 源码路径
ROOT = Path(__file__).parent.parent.parent
LAYOUT_TSX = ROOT / "web" / "app" / "layout.tsx"
TAILWIND_CONFIG = ROOT / "web" / "tailwind.config.ts"
GLOBALS_CSS = ROOT / "web" / "app" / "globals.css"
THEME_TOGGLE = ROOT / "web" / "components" / "ThemeToggle.tsx"
MAINBOARD_TSX = ROOT / "web" / "components" / "MainBoard.tsx"
THEME_LIB = ROOT / "web" / "lib" / "theme.ts"
THEME_CORE_LIB = ROOT / "web" / "lib" / "theme-core.ts"
THEME_TEST_MJS = ROOT / "web" / "scripts" / "test-theme-core.mjs"


def _read(path: Path) -> str:
    assert path.exists(), f"File not found: {path}"
    return path.read_text(encoding="utf-8")


# ===== 1. layout.tsx 必须预设 .dark class (v2 单 dark) =====


def test_layout_has_dark_class_on_html():
    """v2: <html> 必须有 className="dark" — v2 单 dark 主题, 早期脚本决定 + 静态 class 兜底。

    跟 v1 不同的设计:
      v1: 不硬编码, 让早期脚本 (读 localStorage) 决定
      v2: 永远 dark, 早期脚本只加 .dark, 静态 class "dark" 也在 (防 FOUC 二重保险)
    """
    src = _read(LAYOUT_TSX)
    assert 'className="dark"' in src, (
        'v2 layout.tsx 必须 <html className="dark">, '
        "因为 v2 是单 dark 主题, 静态 class 是兜底防 FOUC"
    )


# ===== 2. layout.tsx 早期脚本 + 永远加 .dark =====


def test_layout_has_early_sync_script():
    """早期同步脚本必须在 <head> 里, 同步执行, 加 .dark class 防 FOUC。

    v2 简化: 不再读 localStorage 切 light (永远 dark), 但早期脚本仍要保留
    (SSR hydration 一致性 + 早期设 data-theme 让 getCurrentTheme 立即可读)。
    """
    src = _read(LAYOUT_TSX)
    assert "dangerouslySetInnerHTML" in src, (
        "layout.tsx 必须用 dangerouslySetInnerHTML 注入早期脚本"
    )
    # 早期脚本必须加 .dark class (v2 永远 dark)
    assert "classList.add('dark')" in src or 'classList.add("dark")' in src, (
        "早期脚本必须加 .dark class (v2 单 dark 主题)"
    )
    # 必须移除 .light class (防老用户 localStorage 留 'light' 时元素上还残留 .light)
    assert "classList.remove('light')" in src or 'classList.remove("light")' in src, (
        "早期脚本必须移除 .light class (防老用户残留)"
    )
    # 必须有 data-theme 属性 (getCurrentTheme 读它)
    assert "data-theme" in src, (
        "早期脚本必须设 data-theme 属性 (getCurrentTheme 读它)"
    )
    # 必须设 backgroundColor 防白闪
    assert "backgroundColor" in src, (
        "早期脚本必须设 backgroundColor='#000000' 防白闪"
    )


# ===== 3. layout.tsx 有 suppressHydrationWarning =====


def test_layout_has_suppress_hydration_warning():
    """<html> 必须有 suppressHydrationWarning — 早期脚本改 class 是设计如此。"""
    src = _read(LAYOUT_TSX)
    assert "suppressHydrationWarning" in src, (
        "layout.tsx <html> 标签必须有 suppressHydrationWarning, "
        "否则早期脚本改 className 会触发 React hydration warning"
    )


# ===== 4. layout.tsx themeColor 是纯黑 (v2) =====


def test_layout_has_dark_theme_color():
    """v2: viewport.themeColor 必须是 #000000 (v2 唯一主色, 跟 body 同色)。"""
    src = _read(LAYOUT_TSX)
    assert 'themeColor: "#000000"' in src, (
        'v2 layout.tsx viewport.themeColor 必须是 "#000000" 跟 body bg 同色, '
        "让浏览器原生 UI (地址栏/状态栏) 跟主题色对齐"
    )


# ===== 5. tailwind.config.ts 有 darkMode: 'class' =====


def test_tailwind_dark_mode_class():
    """Tailwind 必须 darkMode: 'class' — 配合 :root 单套变量。"""
    src = _read(TAILWIND_CONFIG)
    assert 'darkMode: "class"' in src, (
        "tailwind.config.ts 必须 darkMode: 'class' (class 策略切主题)"
    )


# ===== 6. tailwind.config.ts colors 用 var() 引用 =====


def test_tailwind_colors_use_css_variables():
    """所有 colors token 必须用 rgb(var(--color-X)) 引用 — 不再硬编码。

    lesson #27 立: 函数形式 color 映射, 防 Tailwind 解析 var() 写死字面量。
    v2 形式: 用 ${opacityValue} 模板插值 (跟 v1 的 `<alpha-value>` 占位符等价,
    Tailwind 同样会传 opacity 进来)。
    """
    src = _read(TAILWIND_CONFIG)
    matches = re.findall(r"var\(--color-[a-z-]+\)", src)
    assert len(matches) >= 8, (
        f"tailwind.config.ts 必须有 ≥8 个 var(--color-...) 引用, "
        f"实际: {len(matches)}"
    )
    # v2 用 ${opacityValue} 模板插值, v1 用 <alpha-value> 占位符, 两种都接受
    has_opacity_interp = "${opacityValue}" in src
    has_alpha_placeholder = "<alpha-value>" in src
    assert has_opacity_interp or has_alpha_placeholder, (
        "Tailwind colors 必须用 alpha 变体模板 (v2: ${opacityValue} 插值, "
        "v1: <alpha-value> 占位符) 才能让 alpha 变体 (bg-X/15) 正确展开"
    )


# ===== 7. tailwind.config.ts safelist 仍存在 =====


def test_tailwind_safelist_preserved():
    """safelist 是 lesson (2026-07-23) 立的防 P0/P2/P3 badge 退化的关键。"""
    src = _read(TAILWIND_CONFIG)
    assert "safelist" in src, (
        "tailwind.config.ts 必须保留 safelist (P0/P2/P3 badge alpha 变体)"
    )


# ===== 8. tailwind.config.ts 有 v2 视觉系统预设 (新) =====


def test_tailwind_has_v2_visual_presets():
    """v2: tailwind config 必须有玻璃拟态 + 发光 + 3D 透视预设。

    - backdropBlur.glass (24px)
    - boxShadow.glass (玻璃卡阴影) + glow-accent* (霓虹绿发光)
    - perspective.card (3D 透视)
    - borderRadius.glass (玻璃大圆角 20px)
    """
    src = _read(TAILWIND_CONFIG)
    required = [
        "backdropBlur",            # 玻璃 blur
        "glass",                   # glass blur 预设
        "glow-accent",             # 霓虹绿发光
        "perspective",             # 3D 透视
        "boxShadow",               # shadow 块
    ]
    for key in required:
        assert key in src, f"v2 tailwind.config.ts 必须有 {key} 块"


# ===== 9. globals.css 有 :root 块 (单主题, 不需要 .dark 块) =====


def test_globals_css_has_root():
    """v2: globals.css 只有 :root 块 (单 dark 主题), 不再有 .dark 块。"""
    src = _read(GLOBALS_CSS)
    assert ":root" in src, "globals.css 必须有 :root 块 (v2 单 dark 主题的变量定义)"


# ===== 10. globals.css :root 至少 12 个 --color- 变量 =====


def test_globals_css_root_has_minimum_variables():
    """:root 必须有 ≥12 个 --color- 变量 (含 bg / fg / border / accent / 4 status + glass token)。"""
    src = _read(GLOBALS_CSS)
    m = re.search(r":root\s*\{([^}]+)\}", src, re.DOTALL)
    assert m, ":root 块缺失"
    root_block = m.group(1)
    matches = re.findall(r"--color-[a-z-]+:", root_block)
    assert len(matches) >= 12, (
        f":root 块必须有 ≥12 个 --color- 变量, 实际: {len(matches)}"
    )


# ===== 11. globals.css 没有 .dark 块 (v2 不需要) =====


def test_globals_css_no_dark_block():
    """v2: 单 dark 主题, 不再有 .dark 块 — 早期脚本只加 .dark class 不依赖 CSS 变量切换。"""
    src = _read(GLOBALS_CSS)
    # .dark 块不能存在 (除了可能的注释或类选择器片段)
    # 简单判定: 没有 ".dark {" 模式
    assert not re.search(r"\.dark\s*\{", src), (
        "v2 globals.css 不应有 .dark 块 — 单 dark 主题, "
        "所有变量在 :root 里, 早期脚本只切 class 不切变量"
    )


# ===== 12. globals.css 不能有硬编码 dark hex =====


def test_globals_css_no_hardcoded_dark_hex():
    """防退化: globals.css 不能有硬编码 dark 色 hex — 必须用 var() 引用。

    v2 调整: 排除 "0 0 0" (三组零, 是 :root 里的 var 值),
    只查 # 开头 hex 字符串 (e.g. #0a0a0a, #1e1e1e)。
    """
    src = _read(GLOBALS_CSS)
    no_block_comments = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    # 排除 /* ... */ 后, 也要排除 // 行注释 (单行 //) — 这里 globals.css 几乎都是 /* */
    forbidden = [
        "#0a0a0a",  # v1 bg-secondary
        "#1e1e1e",  # v1 bg-tertiary
        "#141414",  # v1 bg-secondary alt
        "#2a2a2a",  # v1 border
        "#3a3a3a",  # v1 border-hover
        "#0d0d0d",  # v1 markdown pre bg
        "#0f172a",  # v1 dark bg (slate-900)
        "#1e293b",  # v1 dark bg-secondary (slate-800)
        "#334155",  # v1 dark border (slate-700)
    ]
    for hex_color in forbidden:
        assert hex_color not in no_block_comments, (
            f"globals.css 还有硬编码 {hex_color} — v2 应改用 var(--color-X) 引用"
        )


# ===== 13. globals.css body 颜色用 var() 引用 =====


def test_globals_css_body_uses_var():
    """html, body 的 background / color 必须用 var() 引用。"""
    src = _read(GLOBALS_CSS)
    m = re.search(r"html,\s*body\s*\{([^}]+)\}", src, re.DOTALL)
    assert m, "html, body 块缺失"
    body_block = m.group(1)
    assert "var(--color-bg)" in body_block, (
        "html, body background 必须用 var(--color-bg)"
    )
    assert "var(--color-fg)" in body_block, (
        "html, body color 必须用 var(--color-fg)"
    )


# ===== 14. globals.css 有玻璃拟态 utility class (新) =====


def test_globals_css_has_glass_utilities():
    """v2: globals.css 必须有 .glass / .glass-strong 工具类 (玻璃拟态基础)。"""
    src = _read(GLOBALS_CSS)
    assert ".glass" in src, "globals.css 必须有 .glass 工具类 (玻璃拟态基础)"
    assert ".glass-strong" in src, "globals.css 必须有 .glass-strong (modal/浮层用)"
    assert "backdrop-filter" in src, "globals.css 必须用 backdrop-filter 实现模糊"


# ===== 15. ThemeToggle 组件 =====


def test_theme_toggle_component_exists():
    """v2: ThemeToggle 是只读指示器 (不再是 onClick 按钮)。

    v1: button + onClick + Sun/Moon 切换
    v2: span + 无 onClick + Moon 只读 (因为 v2 单 dark 模式, 切换无意义)

    保留的:
      - data-testid (测试用, v2 改名为 'theme-indicator')
      - lucide 图标 (跟整站 icon 语言一致)
      - data-theme-state 属性 (测试读当前状态)
    """
    src = _read(THEME_TOGGLE)
    # v2: data-testid 是 theme-indicator (主题固定 dark, 改成"指示器"语义)
    assert 'data-testid="theme-indicator"' in src, (
        "v2 ThemeToggle 必须有 data-testid='theme-indicator' "
        "(v1 的 'theme-toggle' 已废, 因为 v2 没有切换动作)"
    )
    # v2: 一定有 data-theme-state 属性
    assert "data-theme-state" in src, (
        "ThemeToggle 必须有 data-theme-state 属性, "
        "让 e2e 测试能读当前主题状态"
    )
    # 必须用 lucide 图标 (跟整站 icon 语言一致)
    assert 'from "lucide-react"' in src, "ThemeToggle 必须用 lucide 图标"
    # v2: Moon 图标 (v1 有 Sun 或 Moon, v2 只用 Moon 表示 dark)
    assert "Moon" in src, "v2 ThemeToggle 必须用 Moon 图标 (单 dark 主题)"


# ===== 16. MainBoard.tsx 挂载 ThemeToggle =====


def test_mainboard_mounts_theme_toggle():
    """MainBoard 顶栏必须挂载 <ThemeToggle /> — 用户至少能看到当前主题状态。"""
    src = _read(MAINBOARD_TSX)
    assert "import { ThemeToggle }" in src or "import {ThemeToggle}" in src, (
        "MainBoard.tsx 必须 import ThemeToggle"
    )
    assert "<ThemeToggle />" in src, "MainBoard.tsx JSX 必须有 <ThemeToggle />"


# ===== 17. lib/theme-core.ts + lib/theme.ts 工具齐 =====


def test_theme_core_lib_has_required_functions():
    """lib/theme-core.ts 必须有: getStoredTheme / setStoredTheme / applyTheme /
    getCurrentTheme / toggleTheme / subscribeTheme / bumpThemeVersion + Theme 类型 + KEY 常量。

    v2 简化: 函数签名还在, 但实现永远返/写 "dark" (no-op 的 toggle 保留签名兼容)。
    """
    src = _read(THEME_CORE_LIB)
    required = [
        "export type Theme",
        "export const THEME_STORAGE_KEY",
        "export const DEFAULT_THEME",
        "export function getStoredTheme",
        "export function setStoredTheme",
        "export function applyTheme",
        "export function getCurrentTheme",
        "export function toggleTheme",
        "export function subscribeTheme",
        "export function bumpThemeVersion",
    ]
    for fn in required:
        assert fn in src, f"lib/theme-core.ts 缺失: {fn}"


def test_theme_lib_reexports_and_has_hook():
    """lib/theme.ts 必须 re-export 纯函数 + 实现 useTheme hook (useSyncExternalStore)。"""
    src = _read(THEME_LIB)
    # re-export 纯函数
    for fn in [
        "getStoredTheme",
        "setStoredTheme",
        "applyTheme",
        "getCurrentTheme",
        "bumpThemeVersion",
        "subscribeTheme",
    ]:
        assert fn in src, f"lib/theme.ts 必须 re-export {fn}"
    # useTheme hook
    assert "export function useTheme" in src, "lib/theme.ts 必须 export useTheme"
    # 用 useSyncExternalStore (多 tab 同步订阅)
    assert "useSyncExternalStore" in src, (
        "useTheme 必须用 useSyncExternalStore (多 tab 同步订阅)"
    )


# ===== 端到端: node 跑 mjs 验证 theme-core 真实行为 =====


def test_end_to_end_theme_core_runs():
    """端到端验证: node 跑 mjs, theme-core 真实行为全过 (v2: 26 个用例)。

    教训 (lesson #2/#15): 单测过 ≠ 真实数据过 — 必须真跑一次。
    v2 简化后用例数从 33 降到 26 (删了 light 翻转相关用例), 但仍要 100% 过。
    """
    assert THEME_TEST_MJS.exists(), f"端到端测试脚本缺失: {THEME_TEST_MJS}"

    node = shutil.which("node")
    assert node, "node 不在 PATH — 端到端测试需要 node 22+ (--experimental-strip-types)"

    result = subprocess.run(
        [node, "--experimental-strip-types", str(THEME_TEST_MJS)],
        capture_output=True,
        text=True,
        cwd=THEME_TEST_MJS.parent.parent,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"theme-core 端到端测试失败 (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "0 failed" in result.stdout, (
        f"theme-core 端到端测试有失败用例:\n{result.stdout}"
    )


# ===== 端到端: 编译产物用 var() (lesson #27 复发检测) =====


def test_compiled_css_uses_css_variables_not_literals():
    """lesson #27 立 (2026-08-02): 锁"编译产物用 var()", 不能再"只 grep 源码字符串"。

    v2 同样适用: 验证 .bg-bg / .text-fg / .border-border 三个最常用 utility
    的编译产物里 `var(--color-)`, **不能是字面量 RGB**。
    """
    import re as _re
    import urllib.request as _ur
    import urllib.error as _ue

    dev_url = "http://localhost:3002/"
    try:
        with _ur.urlopen(dev_url, timeout=5) as resp:
            html = resp.read().decode("utf-8")
    except (_ue.URLError, _ue.HTTPError, TimeoutError) as e:
        pytest.skip(f"dev server 没起来 ({dev_url}): {e} — 本地没起服务就跳过")

    m = _re.search(r"(/_next/static/css/app/layout\.css\?v=\d+)", html)
    assert m, "页面 HTML 里没找到 layout.css?v=xxx 引用 — dev server 没编译好?"
    css_url = "http://localhost:3002" + m.group(1)

    try:
        with _ur.urlopen(css_url, timeout=5) as resp:
            css = resp.read().decode("utf-8")
    except (_ue.URLError, _ue.HTTPError, TimeoutError) as e:
        pytest.skip(f"拉 layout.css 失败: {e}")

    for utility, var_token in [
        (".bg-bg", "--color-bg"),
        (".text-fg", "--color-fg"),
        (".border-border", "--color-border"),
    ]:
        pattern = _re.compile(
            rf"^{_re.escape(utility)}\s*\{{([^}}]*)\}}",
            _re.MULTILINE,
        )
        m = pattern.search(css)
        assert m, f"编译后 CSS 里没找到 {utility} 定义 — 是不是 source 里没用到这个 class?"

        block = m.group(1)
        fix_example = "({ opacityValue }) => opacityValue !== undefined ? `rgb(var(--color-X) / ${opacityValue})` : \"rgb(var(--color-X))\""
        assert f"var({var_token})" in block, (
            f"lesson #27 复发! {utility} 编译产物没引用 {var_token} — Tailwind 把字符串解析了。\n"
            f"  block: {block.strip()[:200]}\n"
            f"  修法: tailwind.config.ts colors.{utility.lstrip('.')} 必须改函数形式\n"
            f"  ({fix_example})"
        )

        literal_pattern = _re.compile(r"rgb\(\d+\s+\d+\s+\d+\s*/")
        assert not literal_pattern.search(block), (
            f"lesson #27 复发! {utility} 编译产物用了字面量 RGB 而不是 var() —\n"
            f"  block: {block.strip()[:200]}\n"
            f"  详见 docs/lessons/05-theme-system.md#27"
        )
