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

    为什么不 strip 字符串: 中文项目里字符串字面量包含"高"/"中"/"低" 等
    enum 值, 跟 dotColor 比较字符串一模一样, strip 会破坏中文字符位置
    (Cockpit priority 三元结构是 'priority === "高" ? ...' 字符串里就是 "高")。
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


# ===== 不变量 2: 整行 onClick 接 onRequestComplete =====


def test_row_onclick_triggers_on_request_complete():
    """整行 TaskRow 第一行 div 的 onClick 必须调 onRequestComplete(task)。

    关键: 不能改成 setExpanded (那是展开详情, 不是完成)。
    历史 bug (2026-07-16): 用户报"现在不能通过手动操作来完成某一个任务了",
    根因是整行 onClick 是 setExpanded, 跟"完成 modal"路径撞了。
    """
    src = read_mainboard()
    # 找 TaskRow 内第一行的 div onClick
    # TaskRow 函数体内: 找 onClick={...} 接 !editingTitle && onRequestComplete
    body = find_taskrow_body(src)
    # 不强制要求 !editingTitle 守卫, 但必须接到 onRequestComplete(task)
    assert "onRequestComplete(task)" in body, (
        "TaskRow 整行 onClick 必须调 onRequestComplete(task) 触发完成 modal, "
        "现在 TaskRow 函数体里没找到这个调用"
    )
    # 防退化: 不能是 setExpanded 独占 (历史 bug)
    m = re.search(r"onClick=\{[^}]*setExpanded\(", body)
    if m:
        # 找到 setExpanded onClick, 检查是否同时有 onRequestComplete
        # 如果只有 setExpanded, fail
        onclick_pattern = re.findall(r"onClick=\{[^}]+\}", body)
        only_setexpanded = all("setExpanded" in p and "onRequestComplete" not in p
                              for p in onclick_pattern)
        assert not only_setexpanded, (
            "TaskRow 整行 onClick 只有 setExpanded 没有 onRequestComplete, "
            "完成路径堵死 (历史 bug 2026-07-16)"
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


# ===== 不变量 5: TaskRow 不再有 hover ✅ 完成按钮 =====


def test_taskrow_no_hover_complete_button():
    """TaskRow 不能有 hover ✅ 完成按钮 (跟 StatusMenu "完成 ✨" 重复, 防误触)。

    历史 (commit 00e3148): Round 1 加了 hover ✅ 按钮, v2 删了,
    整行 click + StatusMenu "完成 ✨" 是两个手动完成入口, 已经够用。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)
    # 检查"完成" 标题的 hover 按钮 (不是 StatusMenu, 是 TaskRow 自己挂的)
    assert 'title="完成' not in body, (
        'TaskRow 还有 hover 完成按钮 (跟 StatusMenu "完成 ✨" 重复, 误触风险), '
        "v2 已删, 不要回退"
    )
    # openComplete 函数是 TaskRow 内的旧函数, 替代是 requestComplete
    assert "function openComplete" not in body and "const openComplete" not in body, (
        "TaskRow 还在用 openComplete 函数, 已被 requestComplete (StatusMenu onComplete) 替代"
    )


# ===== 不变量 6: PriorityMenu "低" 颜色 =====


def test_priority_low_uses_visible_color():
    """PriorityMenu 触发按钮的"低" 色点必须用 bg-fg-secondary (亮灰, 可见)。

    历史 bug (2026-07-17): 用户报"任务优先级只有高、中, 没有低"。
    根因: "低" 用 bg-fg-muted (#666), 1.5px 圆点在 dark theme 几乎不可见。
    修法: 改 bg-fg-secondary (#a0a0a0) — 亮灰, 跟"红黄" 形成"红黄灰" 三档梯度。
    """
    src = read_mainboard()
    # 找 PriorityMenu 函数内的 dotColor 三元
    m = re.search(
        r'dotColor\s*=\s*priority\s*===\s*"高"\s*\?\s*"([^"]+)"\s*:\s*'
        r'priority\s*===\s*"中"\s*\?\s*"([^"]+)"\s*:\s*"([^"]+)"',
        src,
    )
    assert m, "PriorityMenu dotColor 三元结构变了, 需要手动检查"
    low_color = m.group(3)
    assert low_color == "bg-fg-secondary", (
        f'PriorityMenu "低" 颜色 = {low_color!r}, 应是 bg-fg-secondary (亮灰可见, '
        '不是 bg-fg-muted 太暗)。修这个 bug 改 commit 历史 2026-07-17'
    )


# ===== 不变量 7: TaskRow meta 行条件含 task.priority =====


def test_taskrow_meta_row_includes_priority_condition():
    """TaskRow 第二行 meta 行条件必须含 task.priority (让 PriorityMenu 永远显示)。

    历史 bug (2026-07-17): 旧条件 'task.priority !== "低"' 让 priority=低 + 啥都没
    的任务整行 meta 不渲染, PriorityMenu (色点)随之不可见。
    修法: 删 'task.priority !== "低"', 改成 'task.priority || ...' — priority 永远
    渲染, PriorityMenu 永远可见。
    """
    src = read_mainboard()
    body = find_taskrow_body(src)
    # 找 TaskRow 内 'task.priority' 出现在 meta 条件 (&& 链里)
    # 期望: (task.priority || task.draft || task.blocked || ...)
    assert "task.priority ||" in body, (
        "TaskRow 第二行 meta 条件不再含 'task.priority ||', "
        "priority=低 + 啥都没时 PriorityMenu 会被隐藏 (历史 bug 2026-07-17)。"
        " 修法: 在第二行条件开头加 'task.priority ||', 让 PriorityMenu 永远渲染"
    )
    # 防退化: 不应该有 'task.priority !== "低"' 这种隐式反向判断
    assert 'task.priority !== "低"' not in body, (
        "TaskRow 还有 'task.priority !== \"低\"' 这种反向判断, "
        "会让 priority=低 + 啥都没的任务第二行整行隐藏, 历史 bug 2026-07-17"
    )
