"""拖动排序不变量静态分析测试 (2026-07-30 立)。

锁住的 UI 契约 (防退化):
1. ProjectsSection 用 DndContext 包裹项目列表 + onDragEnd 调 reorderProjects
2. SortableProjectCard wrapper 存在 + useSortable
3. ProjectCard 接受 dragHandle prop + 渲染它
4. ProjectCard 内部 task list 用 DndContext 嵌套包裹 (跟外层互不干扰)
5. SortableTaskRow wrapper 存在 + useSortable
6. TaskRow 接受 dragHandle prop + 在第一行最左渲染
7. lib/api.ts 有 reorderProjects / reorderTasks + ProjectSnapshot.sort_order
8. 后端 models 有 ReorderItem / ProjectReorderRequest / TaskReorderRequest
9. 后端 api/projects.py 有 POST /reorder, api/tasks.py 有 POST /reorder
10. storage._next_sort_order / reorder_projects / reorder_tasks 实现存在

设计哲学 (跟 lesson #1/#2/#13 同源):
- 用户报过的"路径堵死" 教训要锁住: 拖动路径同样不允许"看起来做了" 但实际没生效
- SortableContext.items 必须是真 id 数组, 不能传空 list (拖动会失效)
- 后端跨项目拒绝是兜底防线, 不能删除
"""
import re
from pathlib import Path

# 源码路径
ROOT = Path(__file__).parent.parent.parent
MAINBOARD_TSX = ROOT / "web" / "components" / "MainBoard.tsx"
WEB_API_TS = ROOT / "web" / "lib" / "api.ts"
BACKEND_MODELS = ROOT / "app" / "core" / "models.py"
BACKEND_STORAGE = ROOT / "app" / "core" / "storage.py"
BACKEND_API_PROJECTS = ROOT / "app" / "api" / "projects.py"
BACKEND_API_TASKS = ROOT / "app" / "api" / "tasks.py"


def _read(path: Path) -> str:
    assert path.exists(), f"File not found: {path}"
    return path.read_text(encoding="utf-8")


# ===== 1. ProjectsSection 用 DndContext 包裹 + onDragEnd =====


def test_projects_section_uses_dndcontext():
    """ProjectsSection 内部必须用 <DndContext> + <SortableContext> 包住项目列表。"""
    src = _read(MAINBOARD_TSX)
    # 找 ProjectsSection 函数体
    m = re.search(
        r"function ProjectsSection\s*\([^)]*\)[^{]*\{(.*?)^\}",
        src,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "ProjectsSection 函数定义缺失"
    body = m.group(1)
    assert "DndContext" in body, "ProjectsSection 内部必须用 DndContext 包裹项目"
    assert "SortableContext" in body, "ProjectsSection 内部必须用 SortableContext"
    assert "onDragEnd" in body, "ProjectsSection 必须有 onDragEnd handler"
    assert "handleProjectDragEnd" in body, "onDragEnd 必须调 handleProjectDragEnd (命名一致)"


def test_projects_drag_end_calls_reorder_api():
    """handleProjectDragEnd 必须真的调 api.reorderProjects, 不能只是 console.log。"""
    src = _read(MAINBOARD_TSX)
    m = re.search(
        r"const handleProjectDragEnd\s*=[^{]*\{(.*?)^\};",
        src,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "handleProjectDragEnd 函数定义缺失"
    body = m.group(1)
    assert "api.reorderProjects" in body, (
        "handleProjectDragEnd 必须调 api.reorderProjects, 防止 UI 假拖动"
    )
    assert "sort_order" in body, "必须算新 sort_order (不能是空实现)"


# ===== 2. SortableProjectCard wrapper =====


def test_sortable_project_card_exists():
    """SortableProjectCard wrapper 必须存在, 用 useSortable。"""
    src = _read(MAINBOARD_TSX)
    assert "function SortableProjectCard" in src, "SortableProjectCard 函数缺失"
    m = re.search(
        r"function SortableProjectCard\s*\([^)]*\)[^{]*\{(.*?)^\}",
        src,
        re.DOTALL | re.MULTILINE,
    )
    assert m
    body = m.group(1)
    assert "useSortable" in body, "SortableProjectCard 必须调 useSortable"
    assert "CSS.Transform" in body, "必须用 CSS.Transform.toString 转换 transform"
    assert "GripVertical" in body, "拖动 wrapper 必须渲染 GripVertical handle"


# ===== 3. ProjectCard 接受 dragHandle prop =====


def test_project_card_accepts_drag_handle():
    """ProjectCard 必须接受 dragHandle prop, 在第一行渲染。"""
    src = _read(MAINBOARD_TSX)
    # 找 ProjectCard 函数签名 (含 dragHandle)
    m = re.search(
        r"function ProjectCard\s*\(\s*\{(.*?)\}\s*:\s*\{",
        src,
        re.DOTALL,
    )
    assert m, "ProjectCard 函数签名解析失败"
    sig = m.group(1)
    assert "dragHandle" in sig, "ProjectCard 函数签名必须含 dragHandle prop"
    # 必须在第一行 JSX 里被渲染
    assert "{dragHandle}" in src, "ProjectCard 必须在 JSX 里渲染 {dragHandle}"


# ===== 4. ProjectCard 内部 task list 嵌套 DndContext =====


def test_project_card_task_list_uses_nested_dndcontext():
    """ProjectCard 内部 task list 必须有自己的 DndContext (嵌套), 跟外层互不干扰。"""
    src = _read(MAINBOARD_TSX)
    # 找 ProjectCard 内部 task 列表渲染的部分
    m = re.search(
        r"\{expanded && \(\s*<div className=\"px-2 pb-2 pt-1[^>]*>(.*?)</DndContext>",
        src,
        re.DOTALL,
    )
    assert m, "ProjectCard 内部展开区必须用 DndContext 包裹 task list"
    inner = m.group(1)
    assert "SortableContext" in inner, "内层必须有 SortableContext"
    assert "SortableTaskRow" in inner, "内层必须用 SortableTaskRow (不是直接 TaskRow)"
    assert "handleTaskDragEnd" in inner, "内层 onDragEnd 必须调 handleTaskDragEnd"


def test_task_drag_end_calls_reorder_api():
    """handleTaskDragEnd 必须真的调 api.reorderTasks。"""
    src = _read(MAINBOARD_TSX)
    m = re.search(
        r"const handleTaskDragEnd\s*=[^{]*\{(.*?)^\};",
        src,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "handleTaskDragEnd 函数定义缺失"
    body = m.group(1)
    assert "api.reorderTasks" in body, "handleTaskDragEnd 必须调 api.reorderTasks"


# ===== 5. SortableTaskRow wrapper =====


def test_sortable_task_row_exists():
    """SortableTaskRow wrapper 必须存在, 用 useSortable + GripVertical。"""
    src = _read(MAINBOARD_TSX)
    assert "function SortableTaskRow" in src, "SortableTaskRow 函数缺失"
    m = re.search(
        r"function SortableTaskRow\s*\([^)]*\)[^{]*\{(.*?)^\}",
        src,
        re.DOTALL | re.MULTILINE,
    )
    assert m
    body = m.group(1)
    assert "useSortable" in body, "SortableTaskRow 必须调 useSortable"
    assert "CSS.Transform" in body, "必须用 CSS.Transform.toString"
    assert "GripVertical" in body, "必须渲染 GripVertical handle"


# ===== 6. TaskRow 接受 dragHandle prop + 渲染在第一行最左 =====


def test_task_row_accepts_and_renders_drag_handle():
    """TaskRow 必须接受 dragHandle, 在第一行 PriorityMenu 之前渲染。"""
    src = _read(MAINBOARD_TSX)
    # 函数签名
    m = re.search(
        r"function TaskRow\s*\(\s*\{(.*?)\}\s*:\s*\{",
        src,
        re.DOTALL,
    )
    assert m
    sig = m.group(1)
    assert "dragHandle" in sig, "TaskRow 函数签名必须含 dragHandle prop"
    # 必须渲染 (找 {dragHandle} 在 TaskRow 函数体内)
    # 找 TaskRow 函数体范围
    m2 = re.search(
        r"function TaskRow\s*\([^)]*\)[^{]*\{(.*?)^\}",
        src,
        re.DOTALL | re.MULTILINE,
    )
    assert m2
    body = m2.group(1)
    assert "{dragHandle}" in body, "TaskRow 必须在 JSX 渲染 {dragHandle}"


# ===== 7. lib/api.ts 契约 =====


def test_api_ts_has_reorder_projects():
    """lib/api.ts 必须有 api.reorderProjects 方法。"""
    src = _read(WEB_API_TS)
    assert "reorderProjects" in src
    # 用更宽松的 regex 找 reorderProjects 方法体
    m = re.search(
        r"reorderProjects\s*:\s*\([^)]*\)\s*=>\s*request<[^>]+>\s*\(\s*\"([^\"]+)\"",
        src,
    )
    assert m, "api.reorderProjects 函数定义缺失"
    url = m.group(1)
    assert url == "/api/projects/reorder", f"必须 POST /api/projects/reorder, 实际是 {url!r}"
    # 紧接着必须有 method: POST + body JSON.stringify({items: ...})
    m2 = re.search(
        r"reorderProjects\s*:\s*\(.*?\)\s*=>\s*request<[^>]+>\s*\(\s*\"[^\"]+\"\s*,\s*\{(.*?)\}\s*\)",
        src,
        re.DOTALL,
    )
    assert m2, "reorderProjects 整体结构解析失败"
    body = m2.group(1)
    assert "POST" in body, "必须用 POST 方法"
    assert "items" in body, "body 必须含 items 字段"


def test_api_ts_has_reorder_tasks():
    """lib/api.ts 必须有 api.reorderTasks 方法。"""
    src = _read(WEB_API_TS)
    assert "reorderTasks" in src
    m = re.search(
        r"reorderTasks\s*:\s*\([^)]*\)\s*=>\s*request<[^>]+>\s*\(\s*\"([^\"]+)\"",
        src,
    )
    assert m, "api.reorderTasks 函数定义缺失"
    url = m.group(1)
    assert url == "/api/tasks/reorder", f"必须 POST /api/tasks/reorder, 实际是 {url!r}"
    m2 = re.search(
        r"reorderTasks\s*:\s*\(.*?\)\s*=>\s*request<[^>]+>\s*\(\s*\"[^\"]+\"\s*,\s*\{(.*?)\}\s*\)",
        src,
        re.DOTALL,
    )
    assert m2
    body = m2.group(1)
    assert "POST" in body
    assert "items" in body


def test_api_ts_project_has_sort_order():
    """Project interface 必须有 sort_order: number 字段。"""
    src = _read(WEB_API_TS)
    m = re.search(r"export interface Project\s*\{([^}]*)\}", src, re.DOTALL)
    assert m
    assert "sort_order" in m.group(1)
    assert re.search(r"sort_order:\s*number", m.group(1)), (
        "Project.sort_order 必须是 number 类型, 不能是可选 (?) — 后端永远返回"
    )


def test_api_ts_task_has_sort_order():
    """Task interface 必须有 sort_order: number 字段。"""
    src = _read(WEB_API_TS)
    m = re.search(r"export interface Task\s*\{([^}]*)\}", src, re.DOTALL)
    assert m
    assert "sort_order" in m.group(1)
    assert re.search(r"sort_order:\s*number", m.group(1))


def test_api_ts_project_snapshot_has_sort_order():
    """ProjectSnapshot interface 必须有 sort_order: number 字段。"""
    src = _read(WEB_API_TS)
    m = re.search(r"export interface ProjectSnapshot\s*\{([^}]*)\}", src, re.DOTALL)
    assert m
    assert "sort_order" in m.group(1)


# ===== 8. 后端 models 有 ReorderItem / ProjectReorderRequest / TaskReorderRequest =====


def test_backend_models_has_reorder_schemas():
    """后端 models 必须有 ReorderItem / ProjectReorderRequest / TaskReorderRequest。"""
    src = _read(BACKEND_MODELS)
    assert "class ReorderItem" in src, "ReorderItem class 缺失"
    assert "class ProjectReorderRequest" in src, "ProjectReorderRequest class 缺失"
    assert "class TaskReorderRequest" in src, "TaskReorderRequest class 缺失"
    # items 字段必须是 list[ReorderItem]
    m = re.search(r"class ProjectReorderRequest\([^)]*\):\s*(.*?)(?=\nclass |\Z)", src, re.DOTALL)
    assert m
    assert re.search(r"items:\s*list\[ReorderItem\]", m.group(1)), (
        "ProjectReorderRequest.items 必须是 list[ReorderItem]"
    )


# ===== 9. 后端 api/projects.py / api/tasks.py 有 /reorder 端点 =====


def test_api_projects_has_reorder_endpoint():
    """app/api/projects.py 必须有 POST /reorder 端点。"""
    src = _read(BACKEND_API_PROJECTS)
    assert '@router.post("/reorder")' in src, "POST /reorder 端点缺失"
    # 必须用 ProjectReorderRequest
    assert "ProjectReorderRequest" in src
    # 必须调 storage.reorder_projects
    assert "storage.reorder_projects" in src


def test_api_tasks_has_reorder_endpoint():
    """app/api/tasks.py 必须有 POST /reorder 端点。"""
    src = _read(BACKEND_API_TASKS)
    assert '@router.post("/reorder")' in src, "POST /reorder 端点缺失"
    assert "TaskReorderRequest" in src
    assert "storage.reorder_tasks" in src


# ===== 10. storage 实现存在 =====


def test_storage_has_reorder_implementations():
    """storage.py 必须有 reorder_projects / reorder_tasks / _next_sort_order 实现。"""
    src = _read(BACKEND_STORAGE)
    assert "async def reorder_projects" in src, "storage.reorder_projects 缺失"
    assert "async def reorder_tasks" in src, "storage.reorder_tasks 缺失"
    assert "async def _next_sort_order" in src, "storage._next_sort_order 缺失"
    # list 排序必须用 sort_order ASC, created_at ASC (二级 fallback)
    assert "sort_order.asc()" in src, "list 排序必须用 sort_order.asc() 主排序"
    assert "created_at.asc()" in src, "list 排序必须用 created_at.asc() 二级 fallback"


def test_storage_reorder_tasks_rejects_cross_project():
    """storage.reorder_tasks 必须有跨项目拒绝逻辑 (防 task sort_order 跨项目污染)。

    用 Python AST 解析 — 比手写花括号配对稳, dict comprehension / 嵌套 with
    / lambda 都不会骗过深度计数。
    """
    import ast

    src = _read(BACKEND_STORAGE)
    tree = ast.parse(src)
    func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "reorder_tasks":
            func = node
            break
    assert func is not None, "reorder_tasks 函数定义缺失"
    # 把函数体转回 source (含所有子节点的源码)
    body_src = ast.unparse(func)  # type: ignore[attr-defined]
    # 校验逻辑
    assert "project_id" in body_src, "必须查 task.project_id 校验同项目"
    assert "return 0" in body_src, "跨项目必须返回 0 (拒绝)"
    assert "logger.warning" in body_src or "logger.error" in body_src, "跨项目必须记日志"
