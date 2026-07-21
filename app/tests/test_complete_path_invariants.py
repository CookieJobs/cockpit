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


# ===== 不变量 8: StatusMenu 触发按钮是纯色点 (无文字 / 无 ▾ 箭头) =====


def test_statusmenu_trigger_is_pure_dot_no_text_no_chevron():
    """StatusMenu 触发 button 不能渲染状态文字 (未开始/进行中) 也不能渲染 ▾ 箭头。

    2026-07-21 重构: StatusMenu 从 '○ 未开始 ▾' 文字版改成纯色点 button —
      默认 10x10 圆点 (灰/ accent/ 绿), hover ring 高亮, click 弹下拉。
      旧版"○ 未开始 ▾" 三个元素挤在第一行, 跟 PriorityMenu "● 高 ▾" 上下叠,
      一个 task 行 4 个 ▾ 箭头, 视觉噪音爆炸。

    不变量锁住:
    - 触发 button 内不能有 status 文字 (中文"未开始"/"进行中" 是 enum 字符串,
      出现在 button JSX 里就是 bug)
    - 触发 button 内不能有 ChevronDown icon (旧版下拉箭头)
    - 触发 button 内必须有 2x2 / 2.5x2.5 圆点 (色点编码)
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "StatusMenu")

    # 找 StatusMenu 触发 button (第一个 <button ... onClick=... setOpen ... 的 button)
    btn_match = re.search(
        r'<button[\s\S]*?onClick=[\s\S]*?setOpen[\s\S]*?>[\s\S]*?</button>',
        body,
    )
    assert btn_match, "StatusMenu 触发 button 找不到 (期望含 onClick={... setOpen ...})"
    trigger_btn = btn_match.group(0)

    # 不能含 status 文字 — 文字版本会让 task 第一行回到"○ 未开始 ▾" 三件套
    for word in ("未开始", "进行中"):
        assert word not in trigger_btn, (
            f"StatusMenu 触发 button 里出现了状态文字 {word!r}, "
            "2026-07-21 重构要求纯色点形态, 不显示文字。"
            "如需看状态, hover 显示 title 属性即可"
        )
    # 不能有 ChevronDown — 触发 button 不应该有下拉箭头 (色点本身就是 button)
    assert "ChevronDown" not in trigger_btn, (
        "StatusMenu 触发 button 渲染了 ChevronDown 箭头, "
        "2026-07-21 重构要求去掉下拉箭头, 纯色点 button 形态"
    )
    # 必须有色点 (w-2 / w-2.5 rounded-full)
    assert re.search(r"w-2(?:\.5)?\s+h-2(?:\.5)?\s+rounded-full", trigger_btn), (
        "StatusMenu 触发 button 找不到色点 div (期望 w-2/2.5 h-2/2.5 rounded-full), "
        "2026-07-21 重构要求色点编码状态, 不再是单字符 ○◐●"
    )


# ===== 不变量 9: PriorityMenu 触发按钮是纯色点 (无文字 / 无 ▾ 箭头) =====


def test_prioritymenu_trigger_is_pure_dot_no_text_no_chevron():
    """PriorityMenu 触发 button 不能渲染 priority 文字也不能渲染 ▾ 箭头。

    同 StatusMenu 不变量 8 — 同步改成纯色点 button。
    """
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "PriorityMenu")

    btn_match = re.search(
        r'<button[\s\S]*?onClick=[\s\S]*?setOpen[\s\S]*?>[\s\S]*?</button>',
        body,
    )
    assert btn_match, "PriorityMenu 触发 button 找不到"
    trigger_btn = btn_match.group(0)

    # 不能含 priority 文字 — 文字版本会让 task 第一行回到"● 高 ▾" 三件套
    for word in ("高", "中", "低"):
        assert word not in trigger_btn, (
            f"PriorityMenu 触发 button 里出现了 priority 文字 {word!r}, "
            "2026-07-21 重构要求纯色点形态"
        )
    assert "ChevronDown" not in trigger_btn, (
        "PriorityMenu 触发 button 渲染了 ChevronDown 箭头, "
        "2026-07-21 重构要求去掉下拉箭头"
    )
    assert re.search(r"w-2\s+h-2\s+rounded-full", trigger_btn), (
        "PriorityMenu 触发 button 找不到色点 div (期望 w-2 h-2 rounded-full), "
        "2026-07-21 重构要求色点编码 priority"
    )


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
