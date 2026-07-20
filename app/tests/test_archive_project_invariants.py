"""项目归档 UI 不变量静态分析测试 (2026-07-20 立)。

锁住: ProjectsSection / ProjectCard 必须有归档入口, 不能删。
- 完成后 90% 的项目会一直占着 focus 排序, 没归档入口 = 永远清不掉
- 历史坑: 模型层 archived 字段早就有, 工具层 update_project 也支持,
  但 UI 一直缺按钮 — 用户要归档只能走 LLM 工具调用

检查项:
1. ProjectCard 渲染处存在 Archive 按钮 (lucide-react Archive 图标)
2. Archive 按钮触发 updateProject(archived=true)
3. ProjectsSection 有"已归档 N 个"开关 + 渲染归档列表
4. 恢复按钮触发 updateProject(archived=false)
"""
import re
from pathlib import Path

MAINBOARD_TSX = (
    Path(__file__).parent.parent.parent
    / "web"
    / "components"
    / "MainBoard.tsx"
)


def read_mainboard() -> str:
    if not MAINBOARD_TSX.exists():
        raise FileNotFoundError(f"MainBoard.tsx not found at {MAINBOARD_TSX}")
    return MAINBOARD_TSX.read_text(encoding="utf-8")


def _find_function_body_with_ts_types(src: str, name: str) -> str:
    """跨 TS 类型注解提取函数 body（与 test_complete_path_invariants 同款）。"""
    fn_match = re.search(rf"function\s+{re.escape(name)}\s*\(", src)
    if not fn_match:
        raise AssertionError(f"函数 {name!r} 定义未找到")
    i = fn_match.end()
    paren_depth = 1
    while i < len(src) and paren_depth > 0:
        ch = src[i]
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
        elif ch in ('"', "'", "`"):
            quote = ch
            i += 1
            while i < len(src) and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                i += 1
        i += 1
    while i < len(src) and src[i] in " \t\n":
        i += 1
    if i >= len(src) or src[i] != "{":
        raise AssertionError(f"函数 {name!r} 找不到函数体")
    body_start = i
    depth = 0
    j = body_start
    in_string = None
    while j < len(src):
        ch = src[j]
        if in_string:
            if ch == "\\" and j + 1 < len(src):
                j += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in ('"', "'", "`"):
            in_string = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[body_start + 1 : j]
        j += 1
    raise AssertionError(f"函数 {name!r} 括号未闭合")


# ===== 不变量 1: ProjectCard 必须有 Archive 按钮 =====


def test_projectcard_has_archive_button():
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "ProjectCard")
    # Archive 按钮 (lucide-react <Archive size={12} />)
    assert "<Archive" in body, (
        "ProjectCard 没有 Archive 按钮 — 用户没法在 UI 归档已完成项目, "
        "完成后 90% 的项目会一直占着 focus 排序位"
    )
    # title 提示
    assert "归档项目" in body, (
        "ProjectCard Archive 按钮缺 title='归档项目' 提示"
    )


# ===== 不变量 2: Archive 触发 archived=true =====


def test_projectcard_archive_calls_api():
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "ProjectCard")
    # 必须有 handleArchive 函数 + 调 updateProject(id, { archived: true })
    assert "handleArchive" in body, "ProjectCard 缺 handleArchive 函数"
    assert "archived: true" in body, (
        "ProjectCard handleArchive 没传 archived: true — 归档调用错误"
    )
    assert "api.updateProject" in body, "ProjectCard handleArchive 没调 api.updateProject"


# ===== 不变量 3: ProjectsSection 有"已归档 N 个"开关 =====


def test_projects_section_shows_archived_toggle():
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "ProjectsSection")
    # "已归档" 标签 + 计数
    assert "已归档" in body, "ProjectsSection 缺 '已归档' 文本, 用户看不到有归档项目"
    # useSWR 拉 include_archived=true
    assert "include_archived=true" in body, (
        "ProjectsSection 没拉 /api/projects?include_archived=true, 归档列表没数据源"
    )
    # Archive 图标
    assert "<Archive" in body, "ProjectsSection 缺 Archive 图标"


# ===== 不变量 4: 恢复按钮 =====


def test_archived_restore_button():
    src = read_mainboard()
    body = _find_function_body_with_ts_types(src, "ProjectsSection")
    assert "恢复" in body, "ProjectsSection 缺 '恢复' 按钮, 已归档项目无法恢复"
    assert "archived: false" in body, (
        "恢复按钮没传 archived: false — 恢复调用错误"
    )
