"""完成路径不变量静态分析测试 (2026-07-17 立)。

背景:
- Round 1 cycleStatus 设计错误导致"完成路径堵死", 用户报"现在不能通过手动操作
  来完成某一个任务了" (2026-07-16 紧急修复)
- 端点级 pytest (test_api_complete_task.py) 测不到前端 UX 路径
- E2E 需要浏览器引擎 (chromium/playwright), 装依赖太重, 跳过
- 用户明确要求"不装乱七八糟的东西, 直接解决问题"

替代方案: 静态扫 MainBoard.tsx 源码, 检查关键不变量
(编译时保证, 比运行时 E2E 快 10 倍, 也不需要浏览器)

覆盖的不变量 (7 条):
1. onRequestComplete 从 MainBoard 顶层透传到 TaskRow
2. 整行容器 onClick 必须接到 onRequestComplete (防堵死)
3. cycleStatus 函数不能再有 (Round 1 堵死根因)
4. StatusMenu 必须使用 + 下拉里有"完成 ✨" 项
5. TaskRow 不再有 hover ✅ 完成按钮 (跟 StatusMenu "完成 ✨" 重复)
6. PriorityMenu "低" 颜色用 bg-fg-secondary (亮灰可见, 不是 bg-fg-muted)
7. TaskRow 第二行 meta 条件包含 task.priority (priority=低 不会被整行隐藏)

失败信息: 直接告诉用户"哪条不变量破了, 历史哪个 bug, 怎么改"。
"""
import re
from pathlib import Path

# 源码路径 — 跟着项目根走, 不依赖 cwd
MAINBOARD_TSX = (
    Path(__file__).parent.parent.parent
    / "web"
    / "components"
    / "MainBoard.tsx"
)
# PRIORITY_BADGE_STYLES 实际定义在 lib/api.ts (2026-07-23 修):
# 原测试假设它在 MainBoard.tsx 顶层常量, 但实现里搬到 lib/api.ts 模块
# 共享给 MainBoard + /today FocusItem。测试改成扫 lib/api.ts。
WEB_API_TS = (
    Path(__file__).parent.parent.parent
    / "web"
    / "lib"
    / "api.ts"
)


def read_mainboard() -> str:
    """读 MainBoard.tsx 全文, 自动剥掉注释和字符串字面量, 避免误报。

    注释和字符串里出现的代码字面量不该触发"代码不变量"测试。
    返回的源码位置仍跟原文 1:1 对应 (注释/字符串替换成空白, 不删行),
    所以 `_find_function_body_with_ts_types` 的花括号配对仍然正确。
    """
    if not MAINBOARD_TSX.exists():
        raise FileNotFoundError(f"MainBoard.tsx not found at {MAINBOARD_TSX}")
    return _strip_comments_and_strings(MAINBOARD_TSX.read_text(encoding="utf-8"))


def _strip_comments_and_strings(src: str) -> str:
    """把 JS 源码的注释 (// ... 和 /* ... */) 替换成空白, 但**保留字符串字面量完整**。

    为什么不 strip 字符串: 中文项目里字符串字面量包含 priority enum 值
    (历史版本 "高"/"中"/"低", 现在 "P0"/"P1"/"P2"/"P3"), 跟比较字符串一模一样,
    strip 会破坏字符位置。
    """
    out = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        # 行注释
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        # 块注释
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            out.append(" ")
            out.append(" ")
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            i += 2  # 跳过 */
            continue
        # 字符串: **保留原样** (避免破坏中文字符)
        if ch in ('"', "'", "`"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n and src[i] != quote:
                if src[i] == "\\" and i + 1 < n:
                    out.append(src[i])
                    out.append(src[i + 1])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            if i < n:
                out.append(src[i])  # 闭引号
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def find_taskrow_body(src: str) -> str:
    """提取 TaskRow 函数的 body。复用通用版本 (支持 TS 类型注解)。"""
    return _find_function_body_with_ts_types(src, "TaskRow")


# ===== 不变量 1: onRequestComplete 透传 =====


def test_on_request_complete_passed_to_taskrow_render():
    """onRequestComplete 必须从 ProjectsSection 透传到 TaskRow。

    不然 TaskRow 拿不到 onRequestComplete, 整行 click 没法弹 modal。
    """
    src = read_mainboard()
    # ProjectsSection 内 TaskRow 渲染必须有 onRequestComplete={onRequestComplete}
    assert "onRequestComplete={onRequestComplete}" in src, (
        "MainBoard 渲染 TaskRow 处缺失 onRequestComplete={onRequestComplete} 透传, "
        "TaskRow 拿不到弹 4 字段 modal 的入口, 完成路径会堵死"
    )


def test_taskrow_signature_includes_onrequestcomplete():
    """TaskRow 函数签名必须接 onRequestComplete prop。"""
    src = read_mainboard()
    m = re.search(r"function\s+TaskRow\s*\(([^)]*)\)", src)
    assert m, "TaskRow 函数定义未找到"
    sig = m.group(1)
    assert "onRequestComplete" in sig, (
        f"TaskRow 函数签名 {sig!r} 缺 onRequestComplete prop, "
        "整行 click 没法触发完成 modal"
    )


# ===== 不变量 2: 整行 onClick ≠ 完成 (v2 设计, 2026-07-21) =====


def test_row_onclick_does_NOT_trigger_complete():
    """TaskRow 整行第一行 div 的 onClick **不能** 调 onRequestComplete(task)。

    历史背景:
    - v1 (2026-07-17): 整行 onClick = onRequestComplete, 解决 lesson #4 "完成路径堵死"
    - v2 (2026-07-21): 整行 90% 是空白, 空白点中触发完成 modal 反直觉, 用户报
      "红框区域点中不该触发完成"。改为 task-cockpit 原版: 整行 click = toggleExpand。
      完成走 2 个显式入口: StatusMenu popover "完成 ✨" + hover ✅ 按钮。
    - 防退化: 任何把整行 onClick 改回 onRequestComplete 的提交都会被这个不变量拦下。

    这个不变量跟 v1 的 #2 (test_row_onclick_triggers_on_request_complete) 互斥 —
    v1 锁住"整行必须接 onRequestComplete", v2 锁住"整行不能接 onRequestComplete"。
    删 v1 加 v2 (commit 2026-07-21 跟着这次重构)。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)

    # 找第一行主行 (class 含 group/row flex items-center gap-1.5) — 这个 div 是整行 click 容器
    first_row_match = re.search(
        r'(<div\s+className=\{`group/row flex items-center gap-1\.5[^`]*`\}[\s\S]*?</div>)',
        body,
    )
    assert first_row_match, (
        "TaskRow 第一行主行 div 找不到 (期望 class 含 'group/row flex items-center gap-1.5')"
    )
    first_row_div = first_row_match.group(1)

    # 第一行 onClick 不能调 onRequestComplete (v2 反转)
    assert "onRequestComplete" not in first_row_div, (
        "TaskRow 整行 onClick 又调 onRequestComplete 了 — 退回 v1 设计。\n"
        "v1 (2026-07-17): 整行 click = 完成 — 解决 lesson #4 堵死问题。\n"
        "v2 (2026-07-21): 整行 90% 空白, 点空白触发完成反直觉, 用户报红框误触。\n"
        "现在整行 click 必须是 toggleExpand, 完成走 2 个显式入口:\n"
        "  ① StatusMenu popover '完成 ✨' 项\n"
        "  ② hover 第一行时出现的 ✅ 按钮\n"
        "修法: 第一行 onClick 改成 toggleExpand(e), 不要调 onRequestComplete"
    )
    # 整行 onClick 必须接 toggleExpand (v2 设计核心)
    assert re.search(r"onClick=\{[^}]*toggleExpand", first_row_div), (
        "TaskRow 整行 onClick 不是 toggleExpand — v2 设计要求整行 click 切换展开/收起。"
        "修法: onClick={(e) => { if (editingTitle) return; toggleExpand(e); }}"
    )


# ===== 不变量 3: cycleStatus 函数不能再有 =====


def test_no_cyclestatus_function():
    """cycleStatus 函数不能存在 (Round 1 堵死完成路径的根因)。

    历史: cycleStatus 实现 "未开始 ↔ 进行中" 循环, 进行中 → 未开始
    是回退, 永远到不了 "已完成", 加上整行 click 是 setExpanded,
    "完成" 入口被两个 bug 一起堵死。
    """
    src = read_mainboard()
    # 找 function cycleStatus 或 const cycleStatus
    has_fn = bool(re.search(r"function\s+cycleStatus\s*\(", src))
    has_const = bool(re.search(r"const\s+cycleStatus\s*=", src))
    assert not (has_fn or has_const), (
        "cycleStatus 函数被重新加进来了 — 这是 Round 1 堵死完成路径的根因, "
        "状态机改用 StatusMenu 下拉 (commit 00e3148), 不要回退"
    )


# ===== 不变量 4: StatusMenu 存在 + "完成 ✨" 项 =====


def test_statusmenu_is_defined():
    """StatusMenu 必须在 MainBoard.tsx 内部定义 (状态下拉不能删)。

    跟 PriorityMenu / DueEditor 一样, 状态菜单是同文件内定义的组件
    (跟 ChatWindow / CompleteTaskModal 这种从独立文件 import 不一样)。
    检查点: function StatusMenu 定义 + 至少 1 个 useState / 状态下拉项渲染
    """
    src = read_mainboard()
    # function StatusMenu({...}) 定义
    assert re.search(r"function\s+StatusMenu\s*\(", src), (
        "StatusMenu 没在 MainBoard.tsx 定义 — 状态下拉入口缺失"
    )
    # 至少渲染 1 次 (TaskRow 内 <StatusMenu ... />)
    assert "<StatusMenu" in src, (
        "StatusMenu 定义了但没在 TaskRow 渲染 — 状态下拉没接入"
    )


def test_statusmenu_rendered_in_taskrow():
    """StatusMenu 必须在 TaskRow 渲染 (替换原 cycleStatus 按钮)。"""
    src = read_mainboard()
    assert "<StatusMenu" in src, (
        "StatusMenu 没在 TaskRow 渲染, 状态切换入口缺失"
    )


def _find_function_body_with_ts_types(src: str, name: str) -> str:
    """提取函数 body, 跳过 TS 类型注解。

    TS 函数签名 3 种:
    A. function Name(args) { real body }
    B. function Name(args): T { real body }
    C. function Name(args): { type body } { real body }   — 我们 Cockpit 用的

    通用策略: 找函数体 '{' — 它在参数列表 ')' 之后。
    如果签名带 type annotation (形式 C), type body 也在 ')' 之前的花括号对里。
    """
    fn_match = re.search(rf"function\s+{re.escape(name)}\s*\(", src)
    if not fn_match:
        raise AssertionError(f"函数 {name!r} 定义未找到")

    # 找参数 ')' — 跳过 args (含 type body 如果是 C 形式)
    i = fn_match.end()
    paren_depth = 1  # 已开 1 个 '('
    while i < len(src) and paren_depth > 0:
        ch = src[i]
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
        elif ch == '"' or ch == "'" or ch == "`":
            # 跳过字符串
            quote = ch
            i += 1
            while i < len(src) and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                i += 1
            # 跳出 for 循环后 i 指向字符串闭引号
        # '<' '>' 不在 paren 计数, 但类型参数 '<' 会让 paren 平衡失效
        # 实际: TS 函数签名 type body 在 ')' 内, '<' 配对不影响 ')'
        i += 1
    if paren_depth != 0:
        raise AssertionError(f"函数 {name!r} 参数括号不平衡")
    # 现在 i 指向 ')' 之后一位
    # 跳过空白找函数体 '{'
    while i < len(src) and src[i] in " \t\n":
        i += 1
    if i >= len(src) or src[i] != "{":
        raise AssertionError(
            f"函数 {name!r} 找不到函数体 '{{' (签名后看到 {src[i:i+20]!r})"
        )
    body_start = i
    # 配对找函数体 '}' (处理字符串/注释)
    body_end = _find_matching_brace(src, body_start)
    if body_end < 0:
        raise AssertionError(f"函数 {name!r} 函数体未找到匹配的 '}}'")
    return src[body_start + 1 : body_end]


def _skip_brace_pair(src: str, start: int) -> int:
    """从 src[start] 处的 '{' 开始, 配对花括号, 返回匹配的 '}' 位置。"""
    if src[start] != "{":
        return start
    depth = 0
    i = start
    in_string = None
    in_comment = None
    while i < len(src):
        ch = src[i]
        if in_string:
            if ch == "\\" and i + 1 < len(src):
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif in_comment == "line":
            if ch == "\n":
                in_comment = None
        elif in_comment == "block":
            if ch == "*" and i + 1 < len(src) and src[i + 1] == "/":
                in_comment = None
                i += 1
        else:
            if ch == "/" and i + 1 < len(src):
                nxt = src[i + 1]
                if nxt == "/":
                    in_comment = "line"
                    i += 1
                elif nxt == "*":
                    in_comment = "block"
                    i += 1
                else:
                    i += 1
                    continue
            elif ch in ("'", '"', "`"):
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise AssertionError(f"花括号未闭合 (start={start})")


def _find_matching_brace(src: str, start: int) -> int:
    """从 src[start] 处的 '{' 开始, 配对花括号, 返回匹配的 '}' 位置。处理字符串/注释。"""
    return _skip_brace_pair(src, start)


def test_statusmenu_has_complete_item():
    """StatusMenu 下拉必须有"完成" 项 + onComplete 回调 + ✨ 标识。

    这是 4 字段 modal 触发的统一入口, 漏了用户没法完成。
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "StatusMenu")

    assert "完成" in body, 'StatusMenu 下拉里没"完成" 项, 完成入口缺失'
    assert "onComplete" in body, "StatusMenu 下拉里没调 onComplete, 完成 modal 没法触发"
    assert "✨" in body, 'StatusMenu "完成" 项缺 ✨ 标识, 视觉提示用户这一项会弹窗'


# ===== 不变量 5: TaskRow 必须有 hover ✅ 完成按钮 (v2 设计, 2026-07-21) =====


def test_taskrow_must_have_hover_complete_button():
    """TaskRow 必须有 hover ✅ 完成按钮 (作为"完成"显式入口之一)。

    历史:
    - v1 (2026-07-17): 加了 hover ✅ 又删了, 理由"整行 click + StatusMenu 完成项已 2 个入口"
    - v2 (2026-07-21): 整行 click 改成 toggleExpand (不再重复), ✅ 按钮是"完成"
      唯一可见入口之一, 加回。完成路径 = 2 个不重复入口:
        ① StatusMenu 色点 popover "完成 ✨" 项
        ② hover 第一行时出现的 ✅ 按钮 (requestComplete)

    修法: 第一行 hover 出现一个绿色 Check icon button, onClick={requestComplete}。
    title 含"完成" 标识。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)

    # 找第一行主行 (group/row flex items-center gap-1.5) — 用花括号配对找
    # 因为 onClick={(e) => { ... }} 嵌套花括号, 简单 regex 容易误判
    first_row_start = body.find('className={`group/row flex items-center gap-1.5')
    assert first_row_start >= 0, "TaskRow 第一行主行 div 找不到"
    # 找该 div 完整的开标签 — 跳过 className 的 {`...`} 嵌套
    # 简化: className 后面第一个 ` 是模板字符串闭, 然后是 className=,
    # 后面是其他 attr, 直到第一个 > (在 onClick 表达式闭后)
    # 这里用更宽松的方式: 找 onClick 开始到 })(以"onClick={" 后下一个完整的"})} or "{...}>" )
    # 最稳: 找包含 onClick 且以 </div> 结束的大块
    # 取 first_row_start 之后到下一个 "{expanded &&" 之前整段 (后续是第二行 + 展开区)
    end_marker = body.find("{expanded &&", first_row_start)
    if end_marker < 0:
        end_marker = len(body)
    first_row_div = body[first_row_start:end_marker]

    # 第一行内必须有 hover ✅ 完成按钮 — 用更宽松的多条件 AND
    has_request_complete_in_btn = bool(
        re.search(r"<button[\s\S]*?requestComplete\s*\(\s*\)\s*;?[\s\S]*?</button>", first_row_div)
    )
    assert has_request_complete_in_btn, (
        "TaskRow 第一行缺 hover ✅ 完成按钮 — v2 设计要求显式完成入口。\n"
        "修法: 在第一行 hover 区域加 <button onClick={... requestComplete()} "
        'className="opacity-0 group-hover/row:opacity-100 ... hover:text-success ..." '
        'title="标记完成 (弹窗填结果 / CV)">'
        "<Check size={13} /></button>"
    )
    # 找那个 button 整段 (用 Check icon 作为锚点)
    hover_btn_match = re.search(
        r"<button[\s\S]*?onClick[\s\S]*?requestComplete[\s\S]*?</button>",
        first_row_div,
    )
    assert hover_btn_match
    hover_btn = hover_btn_match.group(0)
    # 必须 hover 才出现 (opacity-0 + group-hover/row:opacity-100)
    assert "opacity-0" in hover_btn and "group-hover/row:opacity-100" in hover_btn, (
        "hover ✅ 完成按钮没配 opacity-0 + group-hover/row:opacity-100, "
        "它会一直显示, 视觉跟红框4元素堆叠问题回退"
    )
    # 视觉上暗示"完成" (success 绿)
    assert "text-success" in hover_btn or "hover:text-success" in hover_btn, (
        "hover ✅ 完成按钮缺 success 绿提示, 用户看不出这一项是「完成」 "
        "(vs 删除的 danger 红、展开的 fg 灰)"
    )


# ===== 不变量 6: PriorityMenu 4 档 badge 样式 (2026-07-22 重构) =====


def test_priority_badge_styles_4_levels():
    """PriorityMenu 必须有 4 档 badge 样式 (P0/P1/P2/P3), 颜色饱和度跟紧急度匹配。

    2026-07-22 立: priority 从 3 档 (高/中/低) 升到 4 档 (P0/P1/P2/P3),
    触发 button 从"8x8 纯色点" 重做成"软底色 + 文字 P0/P1/P2/P3" 的 badge 形态。
    锁住 2 件事:
    1. PRIORITY_BADGE_STYLES 必须定义且覆盖全部 4 档
    2. 颜色梯度: P0 红 (最急) / P1 橙 / P2 琥珀 / P3 亮灰 (visible, 跟 lesson #1 对齐)

    历史 bug (2026-07-17): "低" 优先级用 bg-fg-muted (#666) 在 dark theme 几乎
    不可见, 用户报"只有高、中, 没有低"。修法: 改 bg-fg-secondary (#a0a0a0)。
    本不变量继续守: P3 必须保持 bg-fg-secondary 可见, 不回退到 bg-fg-muted。
    """
    src = WEB_API_TS.read_text(encoding="utf-8")
    src = _strip_comments_and_strings(src)

    # 1. PRIORITY_BADGE_STYLES 必须存在并覆盖全部 4 档
    style_match = re.search(
        r'const\s+PRIORITY_BADGE_STYLES\s*:\s*Record<Priority,\s*string>\s*=\s*\{([\s\S]*?)\};',
        src,
    )
    assert style_match, (
        "PRIORITY_BADGE_STYLES 常量找不到 (期望 `const PRIORITY_BADGE_STYLES: "
        "Record<Priority, string> = { ... };`), 2026-07-22 重构要求把 4 档 badge "
        "样式集中到模块级常量, 不要散在 JSX 里。"
    )
    style_body = style_match.group(1)

    # 2. 每档必须存在 + 颜色类正确
    # 2026-07-23 改: P2 从琥珀 (accent) 换冷色蓝 (info), 跟 P1 暖色撞色修掉
    #   红 0° → 橙 30° → 蓝 220°: 跨越色环 ~200°, 一眼区分
    expected = {
        "P0": "bg-danger/15 text-danger border-danger/30",      # 最急 - 红
        "P1": "bg-warning/15 text-warning border-warning/30",  # 高 - 橙
        "P2": "bg-info/15 text-info border-info/30",            # 普通 - 蓝 (冷色, 2026-07-23 换)
        "P3": "bg-fg-secondary/15 text-fg-secondary border-fg-secondary/30",  # 不急 - 亮灰
    }
    for level, expected_classes in expected.items():
        # 简化匹配: 检查每档都存在 + 含其核心颜色
        level_match = re.search(rf'{level}\s*:\s*"([^"]+)"', style_body)
        assert level_match, (
            f"PRIORITY_BADGE_STYLES 缺 {level!r} 档, 4 档必须齐全 "
            "(P0 紧急 / P1 高 / P2 普通 / P3 不急)"
        )
        actual = level_match.group(1)
        # 提取每个档的核心颜色 (bg-* text-* border-* 各一个)
        bg = re.search(r"bg-(\S+?)/15", actual)
        text = re.search(r"text-(\S+?)(?:\s|$)", actual)
        border = re.search(r"border-(\S+?)/30", actual)
        expected_bg, expected_text, expected_border = (
            expected_classes.split()[0].replace("bg-", "").replace("/15", ""),
            expected_classes.split()[1].replace("text-", ""),
            expected_classes.split()[2].replace("border-", "").replace("/30", ""),
        )
        assert bg and bg.group(1) == expected_bg, (
            f"PRIORITY_BADGE_STYLES.{level} bg 应是 bg-{expected_bg}/15, 实际是 "
            f"bg-{bg.group(1) if bg else '?'}/15"
        )
        assert text and text.group(1) == expected_text, (
            f"PRIORITY_BADGE_STYLES.{level} text 应是 text-{expected_text}, 实际是 "
            f"text-{text.group(1) if text else '?'}"
        )
        assert border and border.group(1) == expected_border, (
            f"PRIORITY_BADGE_STYLES.{level} border 应是 border-{expected_border}/30, "
            f"实际是 border-{border.group(1) if border else '?'}/30"
        )

    # 3. P3 必须用 bg-fg-secondary (lesson #1 教训: 不回退到 bg-fg-muted)
    assert "bg-fg-muted" not in style_body, (
        "PRIORITY_BADGE_STYLES 里出现了 bg-fg-muted — 2026-07-17 lesson #1 教训: "
        "低优先级色点用 bg-fg-muted (#666) 在 dark theme 几乎不可见, "
        "必须保持 bg-fg-secondary (#a0a0a0) 亮灰可见。"
    )


def test_priority_badge_uses_p_level_labels():
    """PriorityMenu 触发 button 必须渲染 P0/P1/P2/P3 文字 (badge 形态, 不是纯色点)。

    2026-07-22 v2 重构: 用户反馈 8x8 纯色点看不出是优先级, 跟 StatusMenu 短横条
    区分度低。改成软底色 + 文字 P0/P1/P2/P3 的 badge 形态, 视觉直接读出优先级。

    检测: PriorityMenu 触发 button 必须:
    1. 渲染 P0/P1/P2/P3 文字 (不能只渲染色点, 那是旧 v1 形态)
    2. 不能再渲染 ● 圆点 (w-2 h-2 rounded-full) — 那是旧 v1 形态
    3. 不能有 ChevronDown 箭头 (跟 StatusMenu 一致: 触发 button 永远不带 ▾)
    4. 渲染 PRIORITY_BADGE_STYLES[priority] 样式
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "PriorityMenu")

    btn_match = re.search(
        r'<button[\s\S]*?onClick=[\s\S]*?pop\.toggle[\s\S]*?>[\s\S]*?</button>',
        body,
    )
    assert btn_match, "PriorityMenu 触发 button 找不到 (期望含 onClick={... pop.toggle ...})"
    trigger_btn = btn_match.group(0)

    # 1. 必须渲染 P0/P1/P2/P3 文字 (badge 形态) — 不能渲染 "高/中/低" 旧标签
    assert re.search(r"\{priority\}", trigger_btn), (
        "PriorityMenu 触发 button 没渲染 priority 文字, "
        "2026-07-22 v2 重构要求 badge 必须显示 P0/P1/P2/P3 文字"
    )
    for word in ("高", "中", "低"):
        assert word not in trigger_btn, (
            f"PriorityMenu 触发 button 出现了旧 priority 文字 {word!r}, "
            "2026-07-22 重构已升级为 P0/P1/P2/P3 4 档"
        )

    # 2. 不能有 w-2 h-2 rounded-full 纯色点 (旧 v1 形态)
    assert not re.search(r"w-2\s+h-2\s+rounded-full", trigger_btn), (
        "PriorityMenu 触发 button 还渲染 w-2 h-2 rounded-full 纯色点, "
        "2026-07-22 v2 重构要求 badge 形态 (软底色 + 文字), 不再走纯色点"
    )

    # 3. 不能有 ChevronDown 箭头
    assert "ChevronDown" not in trigger_btn, (
        "PriorityMenu 触发 button 渲染了 ChevronDown 箭头, "
        "2026-07-22 重构要求去掉下拉箭头 (跟 StatusMenu 一致)"
    )

    # 4. 必须用 PRIORITY_BADGE_STYLES[priority] 注入样式
    assert re.search(r"PRIORITY_BADGE_STYLES\[priority\]", trigger_btn), (
        "PriorityMenu 触发 button 没引用 PRIORITY_BADGE_STYLES[priority], "
        "2026-07-22 v2 重构要求从模块级常量取样式, 不在 JSX 内联三元"
    )


def test_priority_popover_renders_p_levels():
    """PriorityMenu popover 必须渲染 P0/P1/P2/P3 4 个选项 (不是旧 3 档 高/中/低)。

    2026-07-22 重构: popover 列表也跟着升 4 档, 每行有 badge + 中文 helper label。
    锁住 popover 数量 = 4 + 渲染的 priority 标签是 P0/P1/P2/P3。
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "PriorityMenu")

    # 1. popover 列表必须是 4 个 P 档 (不是 3 档)
    popover_map = re.search(
        r'\(\["高",\s*"中",\s*"低"\]\s*as\s*const\)\.map', body
    )
    assert not popover_map, (
        "PriorityMenu popover 还在用 `['高', '中', '低']` 旧 3 档列表, "
        "2026-07-22 重构必须升 4 档 P0/P1/P2/P3"
    )
    new_map = re.search(
        r'\(\["P0",\s*"P1",\s*"P2",\s*"P3"\]\s*as\s*const\)\.map', body
    )
    assert new_map, (
        "PriorityMenu popover 找不到 `['P0','P1','P2','P3']` 4 档列表, "
        "2026-07-22 重构要求 popover 渲染 4 档选项"
    )

    # 2. 4 档 priority 文字都要在 popover 里出现
    popover_section = body[body.find("createPortal"):] if "createPortal" in body else body
    for level in ("P0", "P1", "P2", "P3"):
        assert level in popover_section, (
            f"PriorityMenu popover 缺 {level!r} 选项, 4 档必须齐全"
        )


# ===== 不变量 7: PriorityMenu 必须在第一行主行内 (不依赖 meta 行存在) =====


def test_prioritymenu_is_in_first_row_not_meta_row():
    """PriorityMenu 必须在 TaskRow 第一行主行内渲染, 不在第二行 meta 行。

    历史背景:
    - 2026-07-17: PriorityMenu 放在第二行 meta 区, 条件 'task.priority !== "低"'
      让 priority=低 + 啥都没的任务第二行隐藏, PriorityMenu 色点随之不可见 (用户报
      "只有高、中, 没有低")。修法是在 meta 条件加 'task.priority ||'。
    - 2026-07-21: 重构 TaskRow 把 PriorityMenu 上提到第一行纯色点 button。
      meta 行只剩离散事件标签 (草稿/阻塞/checklist/age), 不再需要 priority 兜底。
      不变量现在锁的是"PriorityMenu 在第一行" — 跟"priority 色点永远可见"目标等价
      但更直接 (不依赖 meta 行是否渲染)。

    修法: 在 TaskRow 第一行 `<div className="group/row flex items-center gap-1.5 ...">`
    内 (return 后第一个 flex 容器) 必须有 <PriorityMenu ... />。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)

    # 找第一行主行 (group/row flex) - 新的重构后 class 是 "group/row flex items-center gap-1.5"
    # 同时支持旧的 "flex items-center gap-2" (回归保护)
    first_row_match = re.search(
        r'className=\{`group/row flex items-center gap-1\.5[^`]*`\}',
        body,
    )
    assert first_row_match, (
        "TaskRow 第一行主行 div 找不到 (期望 class 含 'group/row flex items-center gap-1.5'), "
        "可能第一行结构被改坏了, 锁住这个不变量防止回到 'PriorityMenu 藏在 meta 行' 状态"
    )

    # 找第一行结束 (下一个 </div> 之前一段) — 简化: 在第一行 div 开始到下一个 {expanded && (
    # 之间的 JSX 块里必须有 <PriorityMenu
    first_row_start = first_row_match.end()
    # 找下一个 "expanded" 关键节点 (展开区 / 第二行 meta 条件 / return 末尾)
    end_markers = ["{expanded &&", "第二行", "meta"]
    first_row_end = len(body)
    for marker in end_markers:
        idx = body.find(marker, first_row_start)
        if idx > 0 and idx < first_row_end:
            first_row_end = idx
    first_row = body[first_row_start:first_row_end]

    assert "<PriorityMenu" in first_row, (
        "PriorityMenu 不在 TaskRow 第一行主行内 — 当前可能落到了第二行 meta 区。"
        "历史 bug (2026-07-17): priority=低 时色点不可见。"
        "2026-07-21 重构后 PriorityMenu 应在第一行, 跟 StatusMenu 并列, 纯色点 button。"
        "修法: 找到 TaskRow 函数, 把 <PriorityMenu ... /> 移到第一行 flex 容器内"
    )


# ===== 不变量 8: StatusMenu 触发按钮是「融合形态」 — 短进度条 + 阻塞/草稿覆盖 =====


def test_statusmenu_trigger_is_fused_form():
    """StatusMenu 触发 button 必须是「融合形态」, 同一组件多形态表达状态+阻塞/草稿。

    历史:
    - 2026-07-21: StatusMenu 从 '○ 未开始 ▾' 文字版改成纯色点 button。
    - 2026-07-22 v2: 改成"短进度条"形态 (16x4 横向矩形 + 长度按状态), 跟 PriorityMenu
      圆点形状区分。
    - 2026-07-22 v3 (本次): 状态「进行中」用短横条, 状态「阻塞/草稿」用 emoji —
      同一个 button 多形态 (融合), 不再用"第二行独立徽章"表达阻塞/草稿。
      优先级: 阻塞 > 草稿 > 状态。
      阻塞 → 🚧 warning 色, 草稿 → 📝 accent 色, 否则 → 短横条。

    锁住 4 件事:
    1. trigger button JSX 不能含 status 文字 / ChevronDown (跟旧约束一致)
    2. trigger button JSX 必须有 blocked 分支渲染 🚧 emoji
    3. trigger button JSX 必须有 draft 分支渲染 📝 emoji
    4. trigger button JSX 必须有"无修饰"分支渲染 w-4 h-1 rounded-full 横条 track
       + transition-all fill (回退保护 — 没阻塞/草稿时还应该看到原状态进度条)
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "StatusMenu")

    # 找 StatusMenu 触发 button (第一个 <button ... onClick=... pop.toggle ... 的 button)
    btn_match = re.search(
        r'<button[\s\S]*?onClick=[\s\S]*?pop\.toggle[\s\S]*?>[\s\S]*?</button>',
        body,
    )
    assert btn_match, "StatusMenu 触发 button 找不到 (期望含 onClick={... pop.toggle ...})"
    trigger_btn = btn_match.group(0)

    # 1. 不能含 status 文字 / ChevronDown (跟旧约束一致 — 触发 button 永远保持纯色编码)
    for word in ("未开始", "进行中"):
        assert word not in trigger_btn, (
            f"StatusMenu 触发 button 里出现了状态文字 {word!r}, "
            "2026-07-21 重构要求纯色编码形态, 不显示文字。"
            "如需看状态, hover 显示 title 属性即可"
        )
    assert "ChevronDown" not in trigger_btn, (
        "StatusMenu 触发 button 渲染了 ChevronDown 箭头, "
        "2026-07-21 重构要求去掉下拉箭头, 纯色编码 button 形态"
    )

    # 2. blocked 分支必须渲染 🚧 emoji (覆盖状态)
    assert re.search(r"blocked\s*\?\s*\([\s\S]{0,200}🚧[\s\S]{0,200}\)", trigger_btn), (
        "StatusMenu 触发 button 缺 blocked 分支 (期望 blocked ? ( ... 🚧 ... ) : ...), "
        "2026-07-22 v3 重构要求「阻塞」覆盖状态, 同一个 trigger button 多形态表达。"
        "修法: 在 trigger button 内加条件渲染 `blocked ? <span>🚧</span> : ...`"
    )

    # 3. draft 分支必须渲染 📝 emoji (阻塞未命中时的 fallback)
    assert re.search(r"draft\s*\?\s*\([\s\S]{0,200}📝[\s\S]{0,200}\)", trigger_btn), (
        "StatusMenu 触发 button 缺 draft 分支 (期望 draft ? ( ... 📝 ... ) : ...), "
        "2026-07-22 v3 重构要求「草稿」覆盖状态 (阻塞优先), 同一个 trigger button 多形态。"
        "修法: `blocked ? 🚧 : draft ? 📝 : <横条>`"
    )

    # 4. 无修饰 fallback 必须有短进度条形态 (track + fill)
    has_bar_track = re.search(r"w-4\s+h-1\s+rounded-full", trigger_btn)
    has_bar_fill = re.search(r"rounded-full\s+transition-all", trigger_btn)
    assert has_bar_track and has_bar_fill, (
        "StatusMenu 触发 button 找不到「无修饰」状态的短进度条形态 "
        "(期望 w-4 h-1 rounded-full track + transition-all fill), "
        "2026-07-22 v2 横条 + 2026-07-22 v3 融合形态都要求保留这个 fallback。"
        "如果删了横条分支, 没阻塞/草稿时 trigger button 啥都不显示 — bug。"
    )


# ===== 不变量 8b: StatusMenu 必须在 TaskRow 右侧(标题之后, DueEditor 之前) =====


def test_statusmenu_is_in_right_side_of_taskrow():
    """StatusMenu 必须在 TaskRow 第一行**右侧**(DueEditor 之前), 不在左侧。

    历史 (2026-07-22 v3 重构): 之前 StatusMenu(横条) 和 PriorityMenu(圆点) 都堆在
      标题左边, 跟用户说「跟优先级有点重复的感觉」 — 两个色编码控件挤在标题左侧,
      视觉权重不平衡。优先级独占最左位置, 状态指示器挪到右侧跟 due 一起形成
      「右栏」, 用户从右到左扫: 状态+阻塞/草稿 → due → 展开 → hover 按钮。

    检测方法: 在 TaskRow body 里, 找 `<StatusMenu` 和 `<DueEditor` 的字符位置,
      前者必须 < 后者(StatusMenu 在 DueEditor 之前 = 视觉上在 DueEditor 左边 = 右侧)。
      同时 PriorityMenu 必须仍然在 StatusMenu 之前(优先级独占最左, 状态移到右边)。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)

    statusmenu_idx = body.find("<StatusMenu")
    dueditor_idx = body.find("<DueEditor")
    prioritymenu_idx = body.find("<PriorityMenu")

    assert statusmenu_idx > 0, "TaskRow 找不到 <StatusMenu> 渲染"
    assert dueditor_idx > 0, "TaskRow 找不到 <DueEditor> 渲染"
    assert prioritymenu_idx > 0, "TaskRow 找不到 <PriorityMenu> 渲染"

    # 视觉顺序: PriorityMenu (左) → ... → StatusMenu (右) → DueEditor (更右)
    assert prioritymenu_idx < statusmenu_idx, (
        f"PriorityMenu (idx={prioritymenu_idx}) 没在 StatusMenu (idx={statusmenu_idx}) 之前, "
        "2026-07-22 v3 重构要求: 优先级独占最左位置, 状态指示器挪到右侧。\n"
        "修法: TaskRow 第一行 JSX 顺序: <PriorityMenu> ... <StatusMenu> <DueEditor> ..."
    )
    assert statusmenu_idx < dueditor_idx, (
        f"StatusMenu (idx={statusmenu_idx}) 没在 DueEditor (idx={dueditor_idx}) 之前, "
        "2026-07-22 v3 重构要求: 状态指示器在 DueEditor 左边 (右栏内靠左)。\n"
        "修法: TaskRow 第一行 JSX 顺序: <PriorityMenu> ... <StatusMenu> <DueEditor> ..."
    )


# ===== 不变量 8c: TaskRow 第二行 meta 不再有「草稿/阻塞」徽章 =====


def test_taskrow_meta_row_no_draft_blocked_badges():
    """TaskRow 第二行 meta 区不能再渲染「草稿/阻塞」徽章 — 它们已上移到第一行右侧
    的状态融合指示器 (StatusMenu trigger 根据 blocked/draft 切换 🚧/📝/横条)。

    历史 (2026-07-22 v3): 之前 task 阻塞时第二行 meta 区出现一个 `🚧 阻塞` 徽章,
      task 草稿时出现 `📝 草稿` 徽章, 跟第一行左侧的横条状态是「同一维度信息」,
      但分散在两行 + 用两种视觉语言 (横条 vs 徽章) 表达, 反直觉。
      v3 融合后, 阻塞/草稿用同一个 trigger button 的不同形态表达, 不再需要第二行徽章。
      第二行 meta 只剩: checklist 进度 + 「挂了 N 天」提示 (纯事件性 meta)。

    检测方法: TaskRow body 里:
    - 不能有 `{task.draft && (` 这种条件渲染(原来的草稿徽章)
    - 不能有 `{task.blocked && (` 这种条件渲染(原来的阻塞徽章)
    - 不能有 `bg-accent/20 text-accent` 这种徽章 class(原草稿徽章背景色)
    - 不能有 `bg-warning/20 text-warning` 这种徽章 class(原阻塞徽章背景色)
    """
    src = read_mainboard()
    body = find_taskrow_body(src)

    for word, cls in [
        ("草稿徽章", "{task.draft && ("),
        ("阻塞徽章", "{task.blocked && ("),
        ("草稿背景", "bg-accent/20 text-accent"),
        ("阻塞背景", "bg-warning/20 text-warning"),
    ]:
        assert cls not in body, (
            f"TaskRow 找到了 {word} 模式 ({cls!r}), "
            "2026-07-22 v3 融合形态重构要求: 阻塞/草稿已上移到第一行右侧状态指示器, "
            "第二行 meta 不再渲染独立徽章 (避免「同一维度信息分散在两行 + 两种视觉语言」)。\n"
            "修法: 删掉第二行 meta 区的 {task.draft && (...)} 和 {task.blocked && (...)} "
            "两个条件渲染块, meta 条件从 (task.draft || task.blocked || ...) 改成 "
            "(totalCount > 0 || taskAgeDays >= 2) — 只留 checklist 进度和年龄提示。"
        )


# ===== 不变量 9: PriorityMenu 触发按钮是 badge (有 P 档文字 + 软底色) =====
# (2026-07-22 v2 改写: 旧版"纯色点无文字"约束被推翻, 改要求 badge 文字 + 软底色)
# 见 test_priority_badge_uses_p_level_labels  (新不变量 9)


# ===== 不变量 10: TaskRow 第一行 controls (展开/删除) 必须 hover 才显示 =====


def test_taskrow_first_row_controls_are_hover_only():
    """TaskRow 第一行右侧的展开 chevron 和删除按钮必须 hover 才显示 (opacity-0 ... group-hover/row:opacity-100)。

    2026-07-21 重构: TaskRow 第一行视觉极简 — 默认只显示 "色点 + 标题 + due",
    展开/删除等"危险/低频" controls 默认隐藏, hover 第一行才出现。
    防退化: 这些 controls 跟以前一样 opacity-0 ... group-hover:opacity-100,
    但因为外层容器改成 group/row, hover 触发器是 group-hover/row (不是 group-hover)。

    防退化: 不能让展开/删除按钮默认就 100% 可见 — 那会回到红框"4 个元素挤一起"的乱。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)
    first_row_match = re.search(
        r'className=\{`group/row flex items-center gap-1\.5[^`]*`\}',
        body,
    )
    assert first_row_match, "TaskRow 第一行主行 div 找不到"
    first_row_start = first_row_match.end()

    # 找第一行 (到 {expanded && 之前)
    end_markers = ["{expanded &&"]
    first_row_end = len(body)
    for marker in end_markers:
        idx = body.find(marker, first_row_start)
        if idx > 0 and idx < first_row_end:
            first_row_end = idx
    first_row = body[first_row_start:first_row_end]

    # 展开 chevron 按钮必须有 group-hover/row:opacity-100
    assert "group-hover/row:opacity-100" in first_row, (
        "TaskRow 第一行的 controls 没配 group-hover/row:opacity-100, "
        "它们会一直显示, 视觉噪音回到红框'4 个元素挤一起'的状态"
    )
    # 至少有一个 opacity-0 标记 (controls 默认隐藏)
    assert "opacity-0" in first_row, (
        "TaskRow 第一行 controls 缺少 opacity-0 默认隐藏标记, "
        "默认全部显示会让色点编码方案失效"
    )


# ===== 不变量 12: ProjectCard 内"近期已沉淀"子区 (2026-07-22 方案A) =====


def test_project_card_has_recent_achievements_subsection():
    """ProjectCard 展开后必须有"已沉淀 N · 7 天内"子区 (2026-07-22 立, 方案A)。

    背景: complete_task 在 storage 层先写 achievement 再删 task, 看板任务列表
    看不到"刚干完的", 用户切到 /achievements 跨页查又重。方案A 在每个项目卡
    展开态内嵌一个"近期已沉淀"子区, 复用 storage.list_achievements(project, since)。

    不变量锁住:
    - ProjectCard 必须用 useSWR 拉成就 (按 project.name 过滤, since=N 天前)
    - 渲染时必须显示 "已沉淀" 文字标签 + N 天内标签
    - 数据源是 api.listAchievements (前端封装), 不直接 fetch
    - 撤销走 api.undoAchievement (跟 DoneTodaySection 同款)
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "ProjectCard")

    # 1. useSWR 必须拉 /api/achievements 且 since=N 天前
    assert "/api/achievements" in body, (
        "ProjectCard 没有拉 /api/achievements, "
        "2026-07-22 立: 项目卡展开后必须内嵌'近期已沉淀'子区, "
        "缺这个拉取说明回退到'只显示 active tasks' 的旧行为"
    )
    # 2. 必须按 project.name 过滤 (不是 project.id, Achievement.project 存的是 name)
    assert re.search(r"project:\s*project\.name", body), (
        "ProjectCard 拉成就时必须按 project.name 过滤 (不是 project.id), "
        "Achievement ORM 存的是 project.name 字符串, 用 id 过滤会拿不到任何数据"
    )
    # 3. since 必须用动态 N 天前, 不是硬编码 (锁住用 daysAgoISO 工具函数)
    assert "daysAgoISO" in body, (
        "ProjectCard 拉成就时没用 daysAgoISO 工具函数, "
        "since 应该是动态 N 天前, 硬编码日期会随时间过期"
    )
    # 4. 必须显示 "已沉淀" 标签
    assert "已沉淀" in body, (
        "ProjectCard 没有渲染'已沉淀' 标签, "
        "用户没法识别这个子区是干嘛的"
    )
    # 5. 撤销走 api.undoAchievement (跟 DoneTodaySection 一致, 撤销 = 任务回退到任务列表)
    assert re.search(r"api\.undoAchievement", body), (
        "ProjectCard 没接 api.undoAchievement, "
        "误沉淀的成就要能从项目视角一键撤销回到任务列表"
    )
    # 6. Undo2 icon 必须用 (视觉跟 DoneTodaySection 一致)
    assert "Undo2" in body, (
        "ProjectCard '已沉淀' 子区没用 Undo2 按钮, "
        "撤销入口不可见"
    )


# ===== 不变量 13: StatusMenu 末尾有 blocked / draft toggle 入口 (2026-07-22 立) =====


def test_statusmenu_has_blocked_draft_toggle():
    """StatusMenu popover 末尾必须有"阻塞/草稿" toggle 项。

    背景 (2026-07-22): 用户原则 — "凡是 Agent 可以操作的字段, 人也可以操作"。
    Agent 通过 update_task(id, blocked=true|false) 和 update_task(id, draft=true|false)
    能改这两个字段 (见 app/llm/tools.py:168-171), 但前端没手动入口。
    2026-07-22 在 StatusMenu 末尾加分隔 + 两个 toggle 项, 跟"完成 ✨" 同位。

    不变量锁住:
    - StatusMenu 渲染里必须有 data-testid="statusmenu-toggle-blocked" 按钮
    - StatusMenu 渲染里必须有 data-testid="statusmenu-toggle-draft" 按钮
    - 按钮 text 必须是 "标记阻塞"/"解除阻塞" / "标记草稿"/"确认草稿" 四选一动态文案
    - 不能删 data-testid — 后续 E2E 唯一能 stable 锚的就是这个
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "StatusMenu")

    # 1. blocked toggle 按钮
    assert 'data-testid="statusmenu-toggle-blocked"' in body, (
        "StatusMenu 找不到 data-testid=\"statusmenu-toggle-blocked\" 按钮, "
        "2026-07-22 立: blocked 字段必须人手可改, "
        "StatusMenu 末尾的 toggle 是唯一入口 (不放 meta 徽章上避免双入口混乱)"
    )
    # 2. draft toggle 按钮
    assert 'data-testid="statusmenu-toggle-draft"' in body, (
        "StatusMenu 找不到 data-testid=\"statusmenu-toggle-draft\" 按钮, "
        "2026-07-22 立: draft 字段必须人手可改, "
        "StatusMenu 末尾的 toggle 是唯一入口"
    )
    # 3. blocked 动态文案
    assert "标记阻塞" in body and "解除阻塞" in body, (
        "StatusMenu blocked toggle 缺动态文案, "
        "应该是 blocked ? '解除阻塞' : '标记阻塞' (跟 emoji 🚧 配对)"
    )
    # 4. draft 动态文案
    assert "标记草稿" in body and "确认草稿" in body, (
        "StatusMenu draft toggle 缺动态文案, "
        "应该是 draft ? '确认草稿' : '标记草稿' (跟 emoji 📝 配对)"
    )
    # 5. emoji 视觉一致性 — 跟 meta 徽章 (MainBoard.tsx:320 `item.blocked ? "🚧" : "○"`) 用同一套
    assert "🚧" in body, (
        "StatusMenu blocked toggle 没用 🚧 emoji, "
        "跟 meta 区阻塞徽章 (MainBoard.tsx:320) 视觉不一致会让用户联想断掉"
    )
    assert "📝" in body, (
        "StatusMenu draft toggle 没用 📝 emoji, "
        "跟'草稿' 概念在 meta 区用 accent 色, 但 emoji 没显式标记"
    )


def test_statusmenu_signature_accepts_blocked_draft_toggle_props():
    """StatusMenu 函数签名必须接 blocked / draft / onToggleBlocked / onToggleDraft 四个 prop。

    2026-07-22 立: 这四个 prop 是 blocked / draft 字段人手可改的接口, 删了任何
    一个, TaskRow 都传不进去, toggle 就会变成"点了不响应"。
    """
    src = read_mainboard()
    m = re.search(r"function\s+StatusMenu\s*\(([^)]*)\)", src)
    assert m, "StatusMenu 函数定义未找到"
    sig = m.group(1)
    for prop in ("blocked", "draft", "onToggleBlocked", "onToggleDraft"):
        assert prop in sig, (
            f"StatusMenu 函数签名 {sig!r} 缺 {prop!r} prop, "
            f"2026-07-22 立: blocked / draft 字段人手可改, "
            f"StatusMenu 末尾 toggle 必须能触发"
        )


# ===== 不变量 14: TaskRow 透传 blocked / draft 到 StatusMenu (2026-07-22 立) =====


def test_taskrow_passes_blocked_draft_to_statusmenu():
    """TaskRow 渲染 StatusMenu 时必须透传 task.blocked / task.draft + toggle handler。

    2026-07-22 立: TaskRow 调用 StatusMenu 处必须传 4 个 prop:
      blocked={task.blocked}
      draft={task.draft}
      onToggleBlocked={() => updateField("blocked", !task.blocked)}
      onToggleDraft={() => updateField("draft", !task.draft)}

    漏任何一个, 用户点 StatusMenu 末尾 toggle 都不会真改后端, 看起来"点了没反应"。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)
    # TaskRow 渲染 <StatusMenu ... /> 处
    statusmenu_match = re.search(r"<StatusMenu\b[\s\S]*?/>", body)
    assert statusmenu_match, "TaskRow 里 <StatusMenu /> 渲染处找不到"
    call = statusmenu_match.group(0)

    # 1. 透传 blocked={task.blocked}
    assert re.search(r"blocked=\{task\.blocked\}", call), (
        "TaskRow 渲染 <StatusMenu /> 没传 blocked={task.blocked}, "
        "StatusMenu 拿不到当前 blocked 状态, toggle 文案会一直是 '标记阻塞'"
    )
    # 2. 透传 draft={task.draft}
    assert re.search(r"draft=\{task\.draft\}", call), (
        "TaskRow 渲染 <StatusMenu /> 没传 draft={task.draft}, "
        "StatusMenu 拿不到当前 draft 状态, toggle 文案会一直是 '标记草稿'"
    )
    # 3. 透传 onToggleBlocked (用 updateField 通用函数)
    assert re.search(r"onToggleBlocked=\{[^}]*updateField", call), (
        "TaskRow 渲染 <StatusMenu /> 没传 onToggleBlocked handler, "
        "StatusMenu toggle 点了不会真改 blocked 字段"
    )
    # 4. 透传 onToggleDraft
    assert re.search(r"onToggleDraft=\{[^}]*updateField", call), (
        "TaskRow 渲染 <StatusMenu /> 没传 onToggleDraft handler, "
        "StatusMenu toggle 点了不会真改 draft 字段"
    )


def test_taskrow_has_updatefield_helper():
    """TaskRow 内部必须有 updateField 通用函数 (跟 updatePriority / updateDue 同款 PATCH + onChange)。

    updateField 是 blocked / draft 字段的 inline-edit 助手, 跟其他 inline edit
    (updatePriority / updateDue) 走相同的 api.updateTask + onChange() 流程,
    不做乐观更新 (跟 StatusMenu / PriorityMenu / DueEditor 行为一致)。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)
    # updateField 应该是箭头函数: const updateField = async (field, value) => {...}
    assert re.search(
        r"const\s+updateField\s*=\s*async\s*\(\s*field\s*:\s*[\"']blocked[\"']\s*\|\s*[\"']draft[\"']",
        body,
    ), (
        "TaskRow 缺 updateField 通用函数, blocked / draft 字段没法走 PATCH + SWR revalidate 流程"
    )
    # updateField 必须调 api.updateTask (PATCH 语义)
    assert re.search(r"updateField[\s\S]{0,200}api\.updateTask", body), (
        "TaskRow updateField 没调 api.updateTask, "
        "blocked / draft 字段不会真到后端"
    )


# ===== 不变量 16: Popover 抽到共用 hook (2026-07-22 重构) =====


def test_popover_hook_exists_in_separate_file():
    """web/components/Popover.tsx 必须存在并 export usePopover。

    2026-07-22 重构: StatusMenu / PriorityMenu 两个组件原本内联 ~30 行
    useState+useRef+click-outside+Esc 完全重复的样板代码, 抽到
    web/components/Popover.tsx 的 usePopover hook 复用。

    修法 (回退时): 复制下面 popover.tsx 模板回来, import 进 MainBoard.tsx。
    """
    popover_path = MAINBOARD_TSX.parent / "Popover.tsx"
    assert popover_path.exists(), (
        f"web/components/Popover.tsx 找不到 ({popover_path}), "
        "2026-07-22 重构要求把 usePopover hook 抽到独立文件复用, "
        "StatusMenu/PriorityMenu 不应再内联 click-outside 样板代码"
    )
    content = popover_path.read_text(encoding="utf-8")
    assert "usePopover" in content, "web/components/Popover.tsx 必须 export usePopover"
    # 必须实现 click outside (mousedown) + Esc 关闭 + focus trigger
    for needle in ("mousedown", "Escape", "focus()"):
        assert needle in content, (
            f"usePopover 缺 {needle!r} 关键行为, 不再等价于原内联实现"
        )


def test_statusmenu_and_prioritymenu_use_shared_popover_hook():
    """StatusMenu 和 PriorityMenu 必须共用 usePopover (不能各自内联 useState + useEffect)。

    2026-07-22 重构: 抽 usePopover 后两个 menu 都 import + 用 pop.toggle / pop.close。
    防回退到内联 useState(open) + 各自挂 mousedown 监听。

    检测方法: StatusMenu / PriorityMenu 函数体内不应再出现独立的
    `useState(false)` open 状态变量, 也不应再 `document.addEventListener("mousedown", ...)`。
    """
    src = read_mainboard()

    for fn_name in ("StatusMenu", "PriorityMenu"):
        body = _find_function_body_with_ts_types(src, fn_name)
        # 必须有 pop.toggle / pop.close / pop.open 等 hook 用法
        assert re.search(r"\bpop\.", body), (
            f"{fn_name} 函数体里没看到 pop.toggle/pop.close/pop.open 等 hook 用法, "
            "可能没接 usePopover (回退到内联 useState?)"
        )
        # 不应再有内联的 useState(open) 状态变量
        assert not re.search(r"const\s+\[\s*open\s*,\s*setOpen\s*\]\s*=\s*useState", body), (
            f"{fn_name} 体内还有 `const [open, setOpen] = useState(...)` 状态变量, "
            "2026-07-22 重构要求改用 usePopover hook 的 pop.open, 不要再内联 open 状态"
        )
        # 不应再自己 addEventListener("mousedown", ...)
        assert not re.search(r'addEventListener\(\s*[\'"]mousedown[\'"]', body), (
            f"{fn_name} 体内还有 mousedown 监听, "
            "click-outside 应走 usePopover hook 共用, 不要重复实现"
        )


# ===== 不变量 17: Popover 用 Portal 渲染 + fixed 定位 (2026-07-22 立) =====
#
# 背景: 任务在 ProjectCard 展开区底部时, 点 StatusMenu / PriorityMenu 的色点
#   弹出的 popover 会被 ProjectCard 的 `rounded-xl overflow-hidden` **直接裁掉**
#   (CSS 基础: overflow-hidden 无视 z-index, 直接切超界内容)。
#
#   之前用 `absolute left-0 top-6 z-20` 定位 popover, 相对 trigger 容器。
#   在 ProjectCard 内的 trigger, popover 向下展开会超出 ProjectCard 边界,
#   被 overflow-hidden 切掉, 视觉上 = "被项目卡挡住"。
#
# 修法: popover 改用 React Portal (createPortal) 渲染到 document.body,
#   配合 position: fixed 相对视口定位, 跳出任何 overflow / stacking context 限制。
#   位置由 usePopoverPosition hook 算 (getBoundingClientRect + 跟随滚动/resize)。
#
# 锁住的不变量:
# - Popover.tsx 必须 export usePopoverPosition hook (定位计算)
# - StatusMenu / PriorityMenu 体内必须 createPortal 渲染 popover
# - popover 必须用 position: fixed (不能 absolute — 那是回退标志)
# - popover 必须显式设 z-index (默认 50, 必须 > 0)
# - popover 必须挂 popoverRef (让 usePopover click-outside 检测 popover 自身)


def test_popover_hook_exports_usePopoverPosition():
    """web/components/Popover.tsx 必须 export usePopoverPosition。

    2026-07-22 立: 配合 StatusMenu / PriorityMenu 改用 Portal + fixed 定位。
    没有这个 hook, popover 就没法算位置 — 会回退到 absolute top-6 旧方案
    (被 ProjectCard overflow-hidden 裁掉)。
    """
    popover_path = MAINBOARD_TSX.parent / "Popover.tsx"
    content = popover_path.read_text(encoding="utf-8")
    assert "export function usePopoverPosition" in content, (
        "web/components/Popover.tsx 必须 export usePopoverPosition hook, "
        "StatusMenu / PriorityMenu 改 Portal+fixed 定位需要它算 fixed top/left + "
        "跟随滚动/resize"
    )
    # 必须有位置计算 (getBoundingClientRect) + 滚动/resize 监听
    for needle in ("getBoundingClientRect", "scroll", "resize"):
        assert needle in content, (
            f"usePopoverPosition 缺 {needle!r} — 没算位置 / 没跟随滚动"
        )


def test_statusmenu_and_prioritymenu_render_popover_via_portal():
    """StatusMenu / PriorityMenu 的 popover 必须用 createPortal 渲染。

    2026-07-22 立: 不让它们回退到 absolute 定位 (会被 ProjectCard overflow-hidden
    裁掉, 用户报"项目底部的任务点状态弹窗被项目卡挡住")。

    检测方法: StatusMenu / PriorityMenu 函数体内必须 import createPortal + 调用
    createPortal(<popover>, document.body) 把 popover 渲染到 body 下, 跳出
    ProjectCard 的 overflow-hidden 限制。
    """
    src = read_mainboard()

    # 顶部 import 必须有 createPortal
    assert "import { createPortal } from \"react-dom\"" in src, (
        "MainBoard.tsx 顶部必须 `import { createPortal } from \"react-dom\"`, "
        "2026-07-22 重构要求 StatusMenu / PriorityMenu popover 走 Portal 渲染"
    )

    for fn_name in ("StatusMenu", "PriorityMenu"):
        body = _find_function_body_with_ts_types(src, fn_name)
        # 必须有 createPortal 调用
        assert "createPortal" in body, (
            f"{fn_name} 函数体里没看到 createPortal(...) 调用, "
            "popover 必须用 Portal 渲染到 document.body 才能跳出 ProjectCard "
            "overflow-hidden 裁切 (回归 = '项目底部任务点状态弹窗被项目卡挡住')"
        )
        # 必须 render 到 document.body
        assert "document.body" in body, (
            f"{fn_name} 体内没看到 createPortal(..., document.body), "
            "popover Portal 目标必须是 document.body 才能脱离 React 树"
        )


def test_statusmenu_and_prioritymenu_popover_use_fixed_position():
    """StatusMenu / PriorityMenu popover 必须用 position: fixed。

    2026-07-22 立: 防止回退到 absolute (被 ProjectCard overflow-hidden 裁切)。
    Portal + fixed 配合 usePopoverPosition 算的位置 (getBoundingClientRect)
    才能稳定跳出任何 overflow 边界。
    """
    src = read_mainboard()

    for fn_name in ("StatusMenu", "PriorityMenu"):
        body = _find_function_body_with_ts_types(src, fn_name)
        # 必须有 position: "fixed" (style 字符串里)
        assert re.search(r'position:\s*[\'"]fixed[\'"]', body), (
            f"{fn_name} popover 必须用 position: fixed (style inline), "
            "不能用 absolute — absolute 会被 ProjectCard overflow-hidden 裁切"
        )
        # 必须有 zIndex 设置 (默认 50, 至少要 > 0)
        assert re.search(r'zIndex:\s*pos\.zIndex', body), (
            f"{fn_name} popover 必须从 usePopoverPosition 拿 zIndex, "
            "Portal 模式下要靠 inline z-index 跳出 stacking"
        )
        # 不能再用 absolute left-0 top-6 (旧版定位, 旧 bug 标志)
        assert not re.search(r'absolute\s+left-0\s+top-6', body), (
            f"{fn_name} 还残留 `absolute left-0 top-6` 旧版 popover 定位, "
            "必须改成 createPortal + position: fixed (2026-07-22 重构)"
        )


def test_statusmenu_and_prioritymenu_popover_attaches_popoverref():
    """StatusMenu / PriorityMenu popover 根元素必须挂 pop.popoverRef。

    2026-07-22 立: Portal 模式下 popover 渲染到 body 下, 不在 StatusMenu 组件
    树 (containerRef) 子树内。如果 usePopover 的 click-outside 只检测
    containerRef, 点 popover 内部会被误判为"外部点击" → popover 一开就
    被自己关闭。挂 popoverRef 让 click-outside 把 popover 自身也算"内部"。

    修法 (回退时): popover 根 div 必须 `ref={pop.popoverRef}`。
    """
    src = read_mainboard()

    for fn_name in ("StatusMenu", "PriorityMenu"):
        body = _find_function_body_with_ts_types(src, fn_name)
        assert "ref={pop.popoverRef}" in body, (
            f"{fn_name} popover 根 div 缺 `ref={{pop.popoverRef}}`, "
            "Portal 模式下 usePopover click-outside 不知道 popover 边界, "
            "会导致点 popover 内任何按钮都误触关闭"
        )


# ===== 不变量 16: DueEditor 触发 button 永远可见 (2026-07-22 v2 修复) =====


def test_dueditor_trigger_always_visible_no_group_hover():
    """DueEditor 触发 button 必须**永远可见**, 不能依赖 group-hover 隐藏。

    历史背景 (2026-07-22 用户报):
    - "如果这个任务没有时间的话, 我看不到任何能够给这个任务设置截止时间的入口"
    - 旧 DueEditor (v1, 2026-07-17): 无 due 时渲染 📅 emoji 但 class 是
      `opacity-0 group-hover:opacity-100` — 必须 hover 整行才显示
    - 整行 group class 在 v3 (2026-07-21) 从裸 `group` 改成了命名分组 `group/row`,
      同步改所有 hover 控件为 `group-hover/row:opacity-100`, 但 DueEditor **漏改**
    - 结果: 整行根本没有裸 `group` 父级, `group-hover:opacity-100` 找不到对应 group,
      📅 emoji 永远不显示, 用户报告"看不到任何能够给这个任务设置截止时间的入口"
    - v2 修复: DueEditor 改 popover 模式, 触发 button 永远可见 (无 due 时也展示),
      不再依赖任何 group-hover

    锁住 2 件事:
    1. DueEditor 体内不能出现 `group-hover:opacity-100` (v3 漏改 bug 标志)
    2. DueEditor 体内必须包含"无 due"可视元素 (📅 emoji 或"截止"文字), 不能空
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "DueEditor")

    # 1. 不能用旧 group-hover 语法 (v3 漏改 bug 标志)
    assert "group-hover:opacity-100" not in body, (
        "DueEditor 又用回 `group-hover:opacity-100` 旧语法了! "
        "v3 (2026-07-21) 把整行 group class 从 `group` 改成了 `group/row`, "
        "DueEditor 漏改是 2026-07-22 用户报'看不到任何能够给这个任务设置截止时间的入口' "
        "的真实根因。\n"
        "如果用 `group-hover:opacity-100` 又不挂 `group` 父级, "
        "📅 永远不显示, 用户根本点不到设置 due 的入口。\n"
        "修法: DueEditor 触发 button 永远可见, 无 due 时也展示 📅/文字"
    )

    # 2. 无 due 触发元素必须可见 (有 emoji 或文字, 不能空)
    has_visible_no_due = "📅" in body or "截止" in body
    assert has_visible_no_due, (
        "DueEditor 体内没看到 📅 emoji 也没'截止' 文字 — 无 due 触发元素不可见。\n"
        "v2 设计要求触发 button 永远可见, 即便 due=null 也要让用户能点开设置 due"
    )


# ===== 不变量 17: DueEditor popover 必须有 "清除截止日期" 入口 =====


def test_dueditor_popover_has_clear_due_action():
    """DueEditor popover 必须有"清除截止日期" 项 (v2 修复, 2026-07-22)。

    历史背景 (2026-07-22 用户报):
    - "当这个任务一旦有一个截止时间的时候, 我便没有办法再将这个截止时间给去掉"
    - 旧 DueEditor 是 `<input type="date">` 内联编辑 — type=date 的 input 不能
      手动清空成空串, 又没"清除" 按钮, 用户只能 PATCH {due: null}, 但后端
      `if data.due is not None` 把 None 当"未传" 静默吞掉, 双层堵死
    - v2 修复:
      - 前端 DueEditor 改 popover 模式, popover 内加"清除截止日期" 红色按钮
      - 后端 storage.update_task 改用 `data.model_fields_set` 区分未传 vs 传 None
        (端点级测试锁在 test_api_patch_due_null.py)
      - LLM 工具 tool_update_task 改 **kwargs 收集显式传的 null
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "DueEditor")

    # 1. popover 必须有 "清除" 相关的文字 (不强制"截止", 留一定灵活性)
    #   可能形态: "清除截止" / "移除截止" / "清除日期"
    has_clear_label = (
        "清除截止" in body
        or "清除日期" in body
        or "移除截止" in body
        or "取消截止" in body
    )
    assert has_clear_label, (
        "DueEditor popover 缺「清除截止」入口! "
        "用户报: '有截止时间时, 我便没有办法再将这个截止时间给去掉'。\n"
        "v2 修复: popover 内必须有一个红色按钮点一下就 PATCH {due: null}, "
        "显式清除 due 字段。\n"
        "修法: popover 里加个按钮, 文字 '清除截止日期' 之类, onClick 调 onChange(null) + close"
    )

    # 2. 清除按钮必须能调 onChange(null) 真正清空 due
    #   检测: 体内必须出现 onChange(null) 或 onChange?.(null) 的调用
    has_clear_call = re.search(r"onChange\s*\(\s*null\s*\)", body) is not None
    assert has_clear_call, (
        "DueEditor 体内没看到 `onChange(null)` 调用 — 清除按钮即使存在也可能没真清空 due。\n"
        "修法: 清除按钮 onClick 里写 `onChange(null); pop.close();`"
    )

    # 3. 清除按钮走 PATCH {due: null} — onChange 实际被 TaskRow.updateDue 包成
    #    `await api.updateTask(task.id, { due: date })`, 传 null 会被 PATCH 端点接收。
    #    (端点级 PATCH null 行为由 test_api_patch_due_null.py 锁住, 这里只锁前端)


# ===== 不变量 18: DueEditor 必须用 popover 模式 (Portal + usePopover) =====


def test_dueditor_uses_popover_hook():
    """DueEditor 必须用 usePopover + usePopoverPosition (跟 StatusMenu / PriorityMenu 同根)。

    2026-07-22 v2 设计: DueEditor 跟 StatusMenu / PriorityMenu 一样走 popover 模式,
    不用内联 `<input type="date">` 替换。理由:
    - date input 内联替换 → 切完即失焦触发 commit, 流程反人类
      (改完想"清除" 没地方去, 想关又得 Esc)
    - popover 模式 = 一个固定的"操作面板": 改日期 / 清除 / 关, 全在面板内完成
    - 跟 StatusMenu (色点 + 下拉) / PriorityMenu (色点 + 下拉) 视觉风格一致

    锁住 2 件事:
    1. DueEditor 体内必须调 usePopover() (共享 popover 状态机)
    2. DueEditor 体内必须用 createPortal + position: fixed (跟 StatusMenu 同根,
       跳出 ProjectCard overflow-hidden 裁切)
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "DueEditor")

    # 1. 必须用 usePopover 共享 hook
    assert "usePopover()" in body, (
        "DueEditor 没调 `usePopover()` — popover 状态机没复用 Popover.tsx 的 hook, "
        "click-outside / Esc / focus 回到 trigger 全部要自己写一遍, 容易漏。\n"
        "v2 设计: DueEditor 跟 StatusMenu / PriorityMenu 同根, 统一用 usePopover"
    )

    # 2. 必须用 usePopoverPosition (Portal + fixed 定位)
    assert "usePopoverPosition" in body, (
        "DueEditor 没调 `usePopoverPosition` — popover 没用 Portal+fixed 定位, "
        "会被 ProjectCard overflow-hidden 裁掉 (跟 StatusMenu 旧 bug 同根)。\n"
        "修法: `const pos = usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 24 });`"
    )

    # 3. popover 必须用 createPortal 渲染到 document.body
    assert "createPortal" in body, (
        "DueEditor popover 没用 createPortal — 渲染位置可能在 ProjectCard 内部, "
        "被 overflow-hidden 裁切"
    )
    assert "document.body" in body, (
        "DueEditor popover Portal 目标不是 document.body, "
        "可能挂在 ProjectCard 内部, 被 overflow-hidden 裁掉"
    )


# ===== 不变量 19: /today FocusRow 必须用 P0/P1/P2/P3 badge + 左侧竖色条 =====

TODAY_PAGE_TSX = (
    Path(__file__).parent.parent.parent
    / "web"
    / "app"
    / "today"
    / "page.tsx"
)


def read_today_page() -> str:
    """读 /today page.tsx 全文 (含 FocusRow 函数体)。"""
    if not TODAY_PAGE_TSX.exists():
        raise FileNotFoundError(f"today/page.tsx not found at {TODAY_PAGE_TSX}")
    return _strip_comments_and_strings(TODAY_PAGE_TSX.read_text(encoding="utf-8"))


def test_today_focusrow_uses_priority_badge():
    """FocusRow 必须用 PRIORITY_BADGE_STYLES 渲染 P0/P1/P2/P3 软底色 badge (2026-07-23)。

    同步项目列表 (TaskRow) 的优先级表达, 不再用旧 1.5x1.5 小色点 (w-1.5 h-1.5)。
    锁 3 件事:
    1. FocusRow 函数必须存在
    2. body 内必须用 PRIORITY_BADGE_STYLES[focus.priority] 取样式 (跟 TaskRow 共用)
    3. badge 文字必须渲染 {focus.priority} (P0/P1/P2/P3 显式文字, 不是色点)
    4. 不再用旧 w-1.5 h-1.5 小色点形态
    """
    src = read_today_page()
    body = _find_function_body_with_ts_types(src, "FocusRow")

    # 1. 必须用 PRIORITY_BADGE_STYLES (跟 TaskRow 同源)
    assert "PRIORITY_BADGE_STYLES" in body, (
        "FocusRow 没引 PRIORITY_BADGE_STYLES — 没跟项目列表 TaskRow 同步, "
        "可能回退到旧 1.5x1.5 小色点或内联三元判断。\n"
        "修法: `import { PRIORITY_BADGE_STYLES } from \"@/lib/api\"`, "
        "badge 样式用 `${PRIORITY_BADGE_STYLES[focus.priority]}`"
    )

    # 2. badge 必须用 focus.priority 索引 (不是三元)
    assert "PRIORITY_BADGE_STYLES[focus.priority]" in body, (
        "FocusRow 没看到 PRIORITY_BADGE_STYLES[focus.priority] — "
        "可能写错了索引表达式 (例如 focus.priority 写成了 task.priority 或 item.priority)。\n"
        "修法: 跟 TaskRow 一致, 用 PRIORITY_BADGE_STYLES[focus.priority]"
    )

    # 3. badge 文字必须渲染 {focus.priority} (P0/P1/P2/P3 显式文字)
    assert "{focus.priority}" in body, (
        "FocusRow badge 没渲染 P0/P1/P2/P3 文字 — 可能只渲染了色块没文字, "
        "回退到跟项目列表 P0/P1/P2/P3 badge 不一致。\n"
        "修法: badge `<span>{focus.priority}</span>` 显式渲染 P0/P1/P2/P3"
    )

    # 4. 不再用旧 1.5x1.5 小色点
    assert "w-1.5 h-1.5" not in body, (
        "FocusRow 还在用 w-1.5 h-1.5 小色点 — 旧形态, 没跟项目列表 P0/P1/P2/P3 badge 同步。\n"
        "修法: 把色点整段删掉, 替换成 PRIORITY_BADGE_STYLES[focus.priority] 的 badge"
    )


def test_today_focusrow_has_left_priority_bar():
    """FocusRow 必须有左侧竖色条 (3px rounded-full, 颜色按 P0/P1/P2/P3)。

    用户反馈: '最左侧会有一个表示任务优先级的这么一个竖线, 这个竖线会根据优先级的不同
    展示不同的颜色'。竖色条跟 MainBoard FocusItem 同形态, 共享 PRIORITY_BAR_STYLES。

    锁 3 件事:
    1. 容器必须有 relative (给 absolute 色条定位)
    2. 色条 div 必须 absolute + w-[3px] + rounded-full
    3. 色条颜色必须用 PRIORITY_BAR_STYLES[focus.priority] (阻塞 fallback 到 bg-fg-muted/60)
    """
    src = read_today_page()
    body = _find_function_body_with_ts_types(src, "FocusRow")

    # 1. 容器必须是 relative, 给色条 absolute 定位
    #    检查最外层 div 的 className 包含 "relative"
    has_relative_container = re.search(
        r'className\s*=\s*[`"\'].*?relative.*?[`"\']',
        body,
        re.DOTALL,
    ) is not None
    assert has_relative_container, (
        "FocusRow 容器没 `relative` — 左侧色条 absolute 定位没 anchor, "
        "会贴到 body 左边缘而不是卡片左边缘。\n"
        "修法: 外层 div 加 `relative`"
    )

    # 2. 必须有 absolute + w-[3px] + rounded-full 形态的色条
    has_priority_bar_shape = (
        "absolute" in body
        and "w-[3px]" in body
        and "rounded-full" in body
    )
    assert has_priority_bar_shape, (
        "FocusRow 缺左侧竖色条 (absolute + w-[3px] + rounded-full 三件套) — "
        "用户期望'最左侧有表示优先级的竖线', 没这个视觉信号。\n"
        "修法: 加一个色条 div: "
        '`<div className={`absolute left-1.5 top-2.5 bottom-2.5 w-[3px] '
        'rounded-full ${priorityBar}`} aria-hidden />`'
    )

    # 3. 色条必须用 PRIORITY_BAR_STYLES[focus.priority], 阻塞走 bg-fg-muted/60
    assert "PRIORITY_BAR_STYLES" in body, (
        "FocusRow 没用 PRIORITY_BAR_STYLES — 色条颜色可能硬编码或跟 badge 样式混用。\n"
        "修法: `import { PRIORITY_BAR_STYLES } from \"@/lib/api\"`, "
        "色条样式用 PRIORITY_BAR_STYLES[focus.priority]"
    )
    # 阻塞 fallback 必须保留
    assert "bg-fg-muted/60" in body, (
        "FocusRow 缺阻塞 fallback (bg-fg-muted/60) — 阻塞任务的色条颜色没了, "
        "跟 MainBoard FocusItem 阻塞表达不一致。\n"
        "修法: priorityBar = focus.blocked ? 'bg-fg-muted/60' : "
        "PRIORITY_BAR_STYLES[focus.priority]"
    )
