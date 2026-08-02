"""主题切换不变量静态分析测试 (2026-08-01 立)。

锁住 light/dark 主题切换架构, 防退化:
- 早期同步脚本 (防 FOUC) 不能丢
- layout.tsx 不能有硬编码 className="dark"
- tailwind.config.ts 必须 darkMode: 'class' + colors 用 var() 引用
- globals.css 必须有 :root (light) + .dark 双套 CSS variables
- globals.css 不能再有硬编码 dark hex (防漏改)
- ThemeToggle 组件必须挂到 MainBoard 顶栏
- lib/theme.ts + lib/theme-core.ts 工具函数齐
- 端到端 mjs 跑真实验证 (不只锁架构字符串)

设计哲学 (跟 lesson #11/#13/#16 同源):
- 用户报的痛点 (主题不能切) 必须有不变量锁住, 不能光看代码觉得"应该能切"
- 端到端 mjs 是 lesson #2/#15 教训: 单测过 ≠ 真实数据过
- 这里特别加 test_end_to_end_theme_core_runs: 真实 node 跑 mjs, 验证
  纯函数在 mock DOM 下行为正确

覆盖的不变量 (15 条):
1. layout.tsx 没有硬编码 className="dark"
2. layout.tsx 有早期同步脚本 + 读 localStorage
3. layout.tsx 有 suppressHydrationWarning
4. layout.tsx 不再硬编码 themeColor="#0a0a0a"
5. tailwind.config.ts 有 darkMode: "class"
6. tailwind.config.ts colors 用 var() 引用 (至少 4 个 token)
7. tailwind.config.ts safelist 仍存在
8. globals.css 有 :root 和 .dark 两套变量定义
9. globals.css :root 至少 12 个 --color- 变量
10. globals.css .dark 至少 12 个 --color- 变量
11. globals.css 不能有硬编码 dark hex
12. globals.css body 颜色用 var() 引用
13. ThemeToggle 组件存在 + 有 data-testid + import useTheme
14. MainBoard.tsx import ThemeToggle + JSX 渲染 <ThemeToggle />
15. lib/theme-core.ts 工具函数齐 (getStoredTheme / setStoredTheme /
    applyTheme / toggleTheme / useTheme 间接) + lib/theme.ts re-export
+ 端到端: node 跑 mjs, 验证 theme-core 真实行为 (33 用例全过)
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


# ===== 1. layout.tsx 不能硬编码 className="dark" =====


def test_layout_no_hardcoded_dark_class():
    """防退化: layout.tsx 早期脚本决定 class, 不再 hardcode className='dark'。

    lesson 关联: lesson #16 (FOUC/SSR 一致性), 早期脚本必须能跑, server 渲染
    html 标签不能预设 class 让 React hydration 报 warning。

    排除注释行, 注释里可能描述历史值。
    """
    src = _read(LAYOUT_TSX)
    # 删 // ... 行注释
    no_line_comments = "\n".join(
        line for line in src.splitlines() if not line.strip().startswith("//")
    )
    assert 'className="dark"' not in no_line_comments, (
        'layout.tsx 不能再有 className="dark" 硬编码 — '
        "由早期同步脚本 (themeInitScript) 决定 class, "
        "硬编码会导致 React hydration warning"
    )


# ===== 2. layout.tsx 有早期同步脚本 + 读 localStorage =====


def test_layout_has_early_sync_script():
    """早期同步脚本必须在 <head> 里, 同步执行, 读 localStorage 切 class。

    防 FOUC 关键: 必须在 React 渲染前执行, 不依赖 hydration。
    """
    src = _read(LAYOUT_TSX)
    assert "dangerouslySetInnerHTML" in src, (
        "layout.tsx 必须用 dangerouslySetInnerHTML 注入早期脚本"
    )
    # 早期脚本必须读 localStorage key
    assert "localStorage.getItem" in src, (
        "早期脚本必须读 localStorage 拿到主题"
    )
    # 必须有 'cockpit_theme' key
    assert "cockpit_theme" in src, (
        "早期脚本必须用 'cockpit_theme' 作为 localStorage key"
    )
    # 必须有 .dark / .light class 切换
    assert "dark" in src and "light" in src, (
        "早期脚本必须切 .dark / .light class"
    )
    # 必须有 data-theme 属性 (useTheme 读它)
    assert "data-theme" in src, (
        "早期脚本必须设 data-theme 属性 (getCurrentTheme 读它)"
    )


# ===== 3. layout.tsx 有 suppressHydrationWarning =====


def test_layout_has_suppress_hydration_warning():
    """<html> 必须有 suppressHydrationWarning — 早期脚本改 class 是设计如此。"""
    src = _read(LAYOUT_TSX)
    assert "suppressHydrationWarning" in src, (
        "layout.tsx <html> 标签必须有 suppressHydrationWarning, "
        "否则早期脚本改 className 会触发 React hydration warning"
    )


# ===== 4. layout.tsx 不再硬编码 themeColor="#0a0a0a" =====


def test_layout_no_hardcoded_theme_color():
    """viewport.themeColor 是静态 export, 不能跟主题切换; 已移到 CSS color-scheme。"""
    src = _read(LAYOUT_TSX)
    assert 'themeColor: "#0a0a0a"' not in src, (
        "viewport.themeColor 不能再硬编码 dark 色, "
        "应让 CSS color-scheme 决定原生组件颜色 (scrollbar / 表单)"
    )


# ===== 5. tailwind.config.ts 有 darkMode: 'class' =====


def test_tailwind_dark_mode_class():
    """Tailwind 必须 darkMode: 'class' — 配合 :root / .dark 双套变量。"""
    src = _read(TAILWIND_CONFIG)
    assert 'darkMode: "class"' in src, (
        "tailwind.config.ts 必须 darkMode: 'class' (class 策略切主题)"
    )


# ===== 6. tailwind.config.ts colors 用 var() 引用 =====


def test_tailwind_colors_use_css_variables():
    """所有 colors token 必须用 rgb(var(--color-X)) 引用 — 不再硬编码。"""
    src = _read(TAILWIND_CONFIG)
    # bg / fg / border / accent 各 1 个, 4 个 status color (success/warning/danger/info) 各 1 个
    # 至少需要 8 个 var() 引用 (实际有 ~15)
    matches = re.findall(r"var\(--color-[a-z-]+\)", src)
    assert len(matches) >= 8, (
        f"tailwind.config.ts 必须有 ≥8 个 var(--color-...) 引用, "
        f"实际: {len(matches)}"
    )
    # alpha-value 模板必须在 (bg-X/15 自动展开需要)
    assert "<alpha-value>" in src, (
        "Tailwind colors 必须用 'rgb(var(--color-X) / <alpha-value>)' "
        "形式才能让 alpha 变体 (bg-X/15) 正确展开"
    )


# ===== 7. tailwind.config.ts safelist 仍存在 =====


def test_tailwind_safelist_preserved():
    """safelist 是 lesson (2026-07-23) 立的防 P0/P2/P3 badge 退化的关键。"""
    src = _read(TAILWIND_CONFIG)
    assert "safelist" in src, (
        "tailwind.config.ts 必须保留 safelist (P0/P2/P3 badge alpha 变体)"
    )


# ===== 8. globals.css 有 :root 和 .dark 两套变量定义 =====


def test_globals_css_has_root_and_dark():
    """globals.css 必须有 :root (light) + .dark (dark) 两套变量定义。"""
    src = _read(GLOBALS_CSS)
    assert ":root" in src, "globals.css 必须有 :root 块 (light mode 默认变量)"
    assert ".dark" in src, "globals.css 必须有 .dark 块 (dark mode 变量覆盖)"


# ===== 9 & 10. globals.css 变量数量 (双套各 ≥12) =====


def test_globals_css_root_has_minimum_variables():
    """:root 必须有 ≥12 个 --color- 变量 (含 bg / fg / border / accent / 4 status)。"""
    src = _read(GLOBALS_CSS)
    # 抽 :root { ... } 块
    m = re.search(r":root\s*\{([^}]+)\}", src, re.DOTALL)
    assert m, ":root 块缺失"
    root_block = m.group(1)
    matches = re.findall(r"--color-[a-z-]+:", root_block)
    assert len(matches) >= 12, (
        f":root 块必须有 ≥12 个 --color- 变量, 实际: {len(matches)}"
    )


def test_globals_css_dark_has_minimum_variables():
    """.dark 必须有 ≥12 个 --color- 变量。"""
    src = _read(GLOBALS_CSS)
    m = re.search(r"\.dark\s*\{([^}]+)\}", src, re.DOTALL)
    assert m, ".dark 块缺失"
    dark_block = m.group(1)
    matches = re.findall(r"--color-[a-z-]+:", dark_block)
    assert len(matches) >= 12, (
        f".dark 块必须有 ≥12 个 --color- 变量, 实际: {len(matches)}"
    )


# ===== 11. globals.css 不能有硬编码 dark hex =====


def test_globals_css_no_hardcoded_dark_hex():
    """防退化: globals.css 不能有硬编码 dark 色 hex — 必须用 var() 引用。

    漏一处会出现"切到 light 还有一块是黑的" 的视觉断裂。

    排除: 注释行 (// / * ... */) 里的 hex 字面量不查, 注释里引用历史值合理。
    """
    src = _read(GLOBALS_CSS)
    # 删掉 /* ... */ 块注释
    no_block_comments = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    # 原 dark 模式硬编码 hex (应该全部改用 var() 引用)
    forbidden = [
        "#0a0a0a",  # bg
        "#1e1e1e",  # bg-tertiary
        "#141414",  # bg-secondary
        "#2a2a2a",  # border
        "#3a3a3a",  # border-hover
        "#e5e5e5",  # fg
        "#a0a0a0",  # fg-secondary
        "#666666",  # fg-muted
        "#fbbf24",  # accent (dark)
        "#f59e0b",  # accent-hover (dark)
    ]
    # markdown pre 用 #0d0d0d 也算, 一并禁
    forbidden.append("#0d0d0d")
    for hex_color in forbidden:
        assert hex_color not in no_block_comments, (
            f"globals.css 还有硬编码 {hex_color} — 必须改用 var(--color-X) 引用, "
            "否则切到 light 模式这块不会变"
        )


# ===== 12. globals.css body 颜色用 var() 引用 =====


def test_globals_css_body_uses_var():
    """html, body 的 background / color 必须用 var() 引用 (切换时立即变)。"""
    src = _read(GLOBALS_CSS)
    # 找 html, body 块
    m = re.search(r"html,\s*body\s*\{([^}]+)\}", src, re.DOTALL)
    assert m, "html, body 块缺失"
    body_block = m.group(1)
    assert "var(--color-bg)" in body_block, (
        "html, body background 必须用 var(--color-bg), "
        "否则切主题时 body 颜色不变"
    )
    assert "var(--color-fg)" in body_block, (
        "html, body color 必须用 var(--color-fg), "
        "否则切主题时文字颜色不变"
    )


# ===== 13. ThemeToggle 组件 =====


def test_theme_toggle_component_exists():
    """ThemeToggle 组件必须存在, 有 data-testid (测试用) + import useTheme。"""
    src = _read(THEME_TOGGLE)
    assert 'data-testid="theme-toggle"' in src, (
        "ThemeToggle 必须有 data-testid='theme-toggle' (e2e 测试 + 调试用)"
    )
    assert "useTheme" in src, "ThemeToggle 必须 use useTheme hook"
    # 必须有 data-theme-state 属性 (测试可以读当前状态)
    assert "data-theme-state" in src, (
        "ThemeToggle 必须有 data-theme-state 属性, "
        "让 e2e 测试能读当前主题状态"
    )
    # 必须有 onClick 调用 toggle (实际切主题)
    assert "onClick" in src, "ThemeToggle 必须有 onClick handler"
    # 必须有 lucide icon (Sun/Moon) — 跟整站 icon 语言一致
    assert "from \"lucide-react\"" in src, "ThemeToggle 必须用 lucide 图标"


# ===== 14. MainBoard.tsx 挂载 ThemeToggle =====


def test_mainboard_mounts_theme_toggle():
    """MainBoard 顶栏必须挂载 <ThemeToggle /> — 否则用户找不到切入口。"""
    src = _read(MAINBOARD_TSX)
    assert "import { ThemeToggle }" in src or "import {ThemeToggle}" in src, (
        "MainBoard.tsx 必须 import ThemeToggle"
    )
    assert "<ThemeToggle />" in src, "MainBoard.tsx JSX 必须有 <ThemeToggle />"


# ===== 15. lib/theme-core.ts + lib/theme.ts 工具齐 =====


def test_theme_core_lib_has_required_functions():
    """lib/theme-core.ts 必须有: getStoredTheme / setStoredTheme / applyTheme /
    getCurrentTheme / toggleTheme / subscribeTheme / bumpThemeVersion + Theme 类型 + KEY 常量。"""
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
    # 跨 tab 监听 storage 事件
    assert "addEventListener(\"storage\"" in src or "addEventListener('storage'" in src, (
        "lib/theme.ts 必须监听 storage 事件做多 tab 同步"
    )


# ===== 端到端: node 跑 mjs 验证 theme-core 真实行为 =====


def test_end_to_end_theme_core_runs():
    """端到端验证: node 跑 mjs, theme-core 真实行为 33/33 通过。

    教训 (lesson #2/#15): 单测过 ≠ 真实数据过 — 必须真跑一次。
    锁住: mjs 文件存在 + node + strip-types 能解析 .ts + 33 全过。
    """
    # 1. mjs 文件存在
    assert THEME_TEST_MJS.exists(), f"端到端测试脚本缺失: {THEME_TEST_MJS}"

    # 2. node 可用
    node = shutil.which("node")
    assert node, "node 不在 PATH — 端到端测试需要 node 22+ (--experimental-strip-types)"

    # 3. 真跑一次
    result = subprocess.run(
        [node, "--experimental-strip-types", str(THEME_TEST_MJS)],
        capture_output=True,
        text=True,
        cwd=THEME_TEST_MJS.parent.parent,  # web/
        timeout=30,
    )
    # 退出码 0 + 输出含 "33 passed, 0 failed"
    assert result.returncode == 0, (
        f"theme-core 端到端测试失败 (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "0 failed" in result.stdout, (
        f"theme-core 端到端测试有失败用例:\n{result.stdout}"
    )


def test_compiled_css_uses_css_variables_not_literals():
    """lesson #27 立 (2026-08-02): 锁"编译产物用 var()", 不能再"只 grep 源码字符串"。

    背景: v0.3 → v0.4.1 期间, `tailwind.config.ts` colors 用字符串形式
    "rgb(var(--color-X) / <alpha-value>)", Tailwind 3 走 color parser 把
    `var(--color-bg)` fallback 到 .dark 块的当前值 (10 10 10) 写死到产物。
    结果: 组件层所有 `.bg-bg` / `.text-fg` / `.border-border` 都是字面量
    `rgb(10 10 10 / ...)`, 切 html class 也没用 (组件没引用 var, 直接拿 RGB)。

    之前 17 条不变量测试只 grep 源码字符串 (tailwind.config.ts colors 用 var()),
    没去 curl 编译后的 CSS 看产物是不是真有 var() — bug 潜伏 2 周。

    这个测试: 真起 dev server + curl 编译后 CSS, 验证 .bg-bg / .text-fg / .border-border
    三个最常用 utility 的编译产物里 `var(--color-)`, **不能是字面量 RGB**。

    教训 (lesson #2/#15/#17/#27 同源反复犯): 架构层字符串能 grep, 编译产物要真看。
    """
    import re as _re
    import urllib.request as _ur
    import urllib.error as _ue

    # 1. dev server 必须跑 (next dev 在 3002 端口 — AGENTS.md 写的)
    dev_url = "http://localhost:3002/"
    try:
        with _ur.urlopen(dev_url, timeout=5) as resp:
            html = resp.read().decode("utf-8")
    except (_ue.URLError, _ue.HTTPError, TimeoutError) as e:
        pytest.skip(f"dev server 没起来 ({dev_url}): {e} — 本地没起服务就跳过")

    # 2. 找 layout.css?v=xxx 的 URL
    m = _re.search(r"(/_next/static/css/app/layout\.css\?v=\d+)", html)
    assert m, "页面 HTML 里没找到 layout.css?v=xxx 引用 — dev server 没编译好?"
    css_url = "http://localhost:3002" + m.group(1)

    # 3. 拉 CSS
    try:
        with _ur.urlopen(css_url, timeout=5) as resp:
            css = resp.read().decode("utf-8")
    except (_ue.URLError, _ue.HTTPError, TimeoutError) as e:
        pytest.skip(f"拉 layout.css 失败: {e}")

    # 4. 验证三个最关键 utility 用 var() (不能用字面量 RGB)
    #    lesson #27 的具体症状: ".bg-bg { background-color: rgb(10 10 10 / ...); }"
    #    期望: ".bg-bg { background-color: rgb(var(--color-bg) / ...); }"
    for utility, var_token in [
        (".bg-bg", "--color-bg"),
        (".text-fg", "--color-fg"),
        (".border-border", "--color-border"),
    ]:
        # 找 utility 定义块:  ".bg-bg {" 后 1-3 行内的 "background-color:" 或 "color:" 或 "border-color:"
        # 用非贪婪匹配, 抓到首个 block
        pattern = _re.compile(
            rf"^{_re.escape(utility)}\s*\{{([^}}]*)\}}",
            _re.MULTILINE,
        )
        m = pattern.search(css)
        assert m, f"编译后 CSS 里没找到 {utility} 定义 — 是不是 source 里没用到这个 class?"

        block = m.group(1)
        # 期望: block 里包含 var(--color-X) 引用
        fix_example = "({ opacityValue }) => opacityValue !== undefined ? `rgb(var(--color-X) / ${opacityValue})` : \"rgb(var(--color-X))\""
        assert f"var({var_token})" in block, (
            f"lesson #27 复发! {utility} 编译产物没引用 {var_token} — Tailwind 把字符串解析了。\n"
            f"  block: {block.strip()[:200]}\n"
            f"  修法: tailwind.config.ts colors.{utility.lstrip('.')} 必须改函数形式\n"
            f"  ({fix_example})"
        )

        # 防御: 不能是字面量 RGB
        # (RGB 字面量 = "rgb(数字 数字 数字 /" 的形式, e.g. "rgb(10 10 10 /")
        literal_pattern = _re.compile(r"rgb\(\d+\s+\d+\s+\d+\s*/")
        assert not literal_pattern.search(block), (
            f"lesson #27 复发! {utility} 编译产物用了字面量 RGB 而不是 var() —\n"
            f"  block: {block.strip()[:200]}\n"
            f"  详见 docs/lessons/05-theme-system.md#27"
        )
