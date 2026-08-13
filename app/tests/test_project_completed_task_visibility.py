"""Project-local completed-task visibility invariants."""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
MAINBOARD = ROOT / "web" / "components" / "MainBoard.tsx"
API_TYPES = ROOT / "web" / "lib" / "api.ts"
BACKEND_MODELS = ROOT / "app" / "core" / "models.py"


def read(path: Path) -> str:
    assert path.exists(), f"Missing source file: {path}"
    return path.read_text(encoding="utf-8")


def function_body(src: str, name: str) -> str:
    start = src.find(f"function {name}(")
    assert start >= 0, f"function {name} is missing"
    index = start + len(f"function {name}(")
    paren_depth = 1
    quote = None
    while index < len(src) and paren_depth:
        char = src[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        index += 1
    assert paren_depth == 0, f"function {name} parameters are not balanced"
    while index < len(src) and src[index].isspace():
        index += 1
    assert index < len(src) and src[index] == "{", f"function {name} has no body"
    body_start = index
    depth = 0
    quote = None
    index = body_start
    while index < len(src):
        char = src[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return src[body_start + 1:index]
        index += 1
    raise AssertionError(f"function {name} body is not balanced")


def test_project_snapshot_contract_exposes_done_tasks():
    assert "done_tasks: list[Task]" in read(BACKEND_MODELS)
    assert "done_tasks: Task[];" in read(API_TYPES)


def test_project_card_keeps_active_work_before_completed_history():
    body = function_body(read(MAINBOARD), "ProjectCard")
    assert "const activeTasks = project.tasks" in body
    assert "const completedTasks = project.done_tasks" in body
    assert "const totalTaskCount = activeTasks.length + completedTasks.length" in body
    assert "{doneCount}" in body
    assert "/{totalTaskCount}" in body
    assert "items={activeTasks.map((t) => t.id)}" in body
    assert "{completedTasks.length > 0 && (" in body
    assert "<CompletedTaskRow" in body
    assert body.index("添加任务") < body.index("completedTasks.length > 0")


def test_completed_rows_only_offer_confirmed_task_undo():
    body = function_body(read(MAINBOARD), "CompletedTaskRow")
    assert "task.completed_at" in body
    assert "line-through" in body
    assert "api.undoTask(task.id)" in body
    assert "confirm(`撤销" in body
    assert "onChange()" in body
    assert "SortableTaskRow" not in body
    assert "onRequestComplete" not in body


def test_legacy_global_completed_view_is_removed():
    assert "function LegacyCompletedTaskView" not in read(MAINBOARD)
