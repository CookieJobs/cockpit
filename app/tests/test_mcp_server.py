"""MCP server 端到端测试 (v0.5a 立, 2026-08-02).

mcp 2.0 协议: stdio transport 用 **line-delimited JSON** (一行一个 JSON-RPC 请求/响应).
不是 Content-Length header (那是 legacy).

测法: subprocess 启动 mcp_server + 发 JSON-RPC 行 + 读响应行.

覆盖:
  1. initialize + 5 个工具都列出来
  2. list_projects (空 db 返空)
  3. add_task + list_tasks 端到端
  4. complete_task 端到端 (沉淀成就)
  5. list_achievements 端到端
  6. 完整工作流 (add → complete → list)
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# 项目根 (跑 pytest 时 cwd = cockpit/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _start_mcp_server(db_path: str) -> subprocess.Popen:
    """启动 mcp_server subprocess, stdio transport, 用指定 db."""
    env = os.environ.copy()
    env["COCKPIT_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    return subprocess.Popen(
        [sys.executable, "-m", "app.mcp_server"],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
    )


def _send_request(proc: subprocess.Popen, method: str, params=None, req_id: int = 1) -> dict:
    """发一个 line-delimited JSON-RPC 请求, 读回响应 (1 行)."""
    msg = json.dumps({
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    })
    proc.stdin.write(msg + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError(f"no response for {method}, stderr: {proc.stderr.read()}")
    return json.loads(line)


def _send_notification(proc: subprocess.Popen, method: str, params=None):
    """发 JSON-RPC notification (无 id, 不期待响应)."""
    msg = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
    })
    proc.stdin.write(msg + "\n")
    proc.stdin.flush()


def _terminate(proc: subprocess.Popen):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture
def mcp_server():
    """启动 MCP server 用 temp db, 测完 cleanup. 已发 initialize + initialized."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    Path(db_path).unlink()

    proc = _start_mcp_server(db_path)
    try:
        # initialize (握手, 必发)
        init_resp = _send_request(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.0.1"},
        })
        assert "result" in init_resp, f"initialize failed: {init_resp}\nstderr: {proc.stderr.read()}"
        # initialized notification (MCP 协议要求)
        _send_notification(proc, "notifications/initialized")
        yield proc, db_path
    finally:
        _terminate(proc)
        if os.path.exists(db_path):
            os.unlink(db_path)


# ============================================================================
# 1. initialize + list tools
# ============================================================================

def test_mcp_server_lists_5_tools(mcp_server):
    """v0.5a: 启动后 list tools 必含 5 个核心工具."""
    proc, _ = mcp_server
    resp = _send_request(proc, "tools/list", {}, req_id=2)
    assert "result" in resp, f"tools/list failed: {resp}"
    tools = resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}
    expected = {"list_projects", "list_tasks", "add_task", "complete_task", "list_achievements"}
    assert expected.issubset(tool_names), f"missing tools: {expected - tool_names}, got {tool_names}"
    assert len(tools) == 5, f"expected exactly 5 tools, got {len(tools)}: {tool_names}"


def test_mcp_each_tool_has_input_schema(mcp_server):
    """每个工具必含 inputSchema (MCP 协议要求)."""
    proc, _ = mcp_server
    resp = _send_request(proc, "tools/list", {}, req_id=3)
    tools = resp["result"]["tools"]
    for t in tools:
        assert "inputSchema" in t, f"tool {t.get('name')} missing inputSchema"
        assert "description" in t, f"tool {t.get('name')} missing description"


# ============================================================================
# 2. list_projects 空 db
# ============================================================================

def test_mcp_list_projects_empty_db(mcp_server):
    """空 db → list_projects 返空数组."""
    proc, _ = mcp_server
    resp = _send_request(proc, "tools/call", {
        "name": "list_projects",
        "arguments": {},
    }, req_id=4)
    assert "result" in resp, f"call failed: {resp}"
    content = resp["result"]["content"]
    assert len(content) == 1
    projects = json.loads(content[0]["text"])
    assert projects == []


# ============================================================================
# 3. add_task 端到端
# ============================================================================

def test_mcp_add_task_then_list(mcp_server):
    """add_task → list_tasks 应该能看到."""
    proc, db_path = mcp_server
    # 1. 先建项目 (通过 storage 直接, mcp 暂不暴露 create_project)
    from app.core import storage
    from app.core.models import ProjectCreate

    async def _setup():
        storage.init_engine(database_url=f"sqlite+aiosqlite:///{db_path}")
        await storage.create_tables()
        p = await storage.add_project(ProjectCreate(name="测试项目"))
        return p.id

    project_id = asyncio.run(_setup())

    # 2. mcp add_task
    resp = _send_request(proc, "tools/call", {
        "name": "add_task",
        "arguments": {
            "project_id": project_id,
            "title": "MCP 测试任务",
            "priority": "P1",
        },
    }, req_id=5)
    assert "result" in resp, f"add_task failed: {resp}"
    content = resp["result"]["content"]
    task_result = json.loads(content[0]["text"])
    assert task_result["title"] == "MCP 测试任务"
    assert task_result["priority"] == "P1"
    assert "id" in task_result

    # 3. mcp list_tasks 验证
    resp = _send_request(proc, "tools/call", {
        "name": "list_tasks",
        "arguments": {"project_id": project_id},
    }, req_id=6)
    tasks = json.loads(resp["result"]["content"][0]["text"])
    assert len(tasks) == 1
    assert tasks[0]["title"] == "MCP 测试任务"


# ============================================================================
# 4. complete_task 端到端
# ============================================================================

def test_mcp_complete_task_creates_achievement(mcp_server):
    """complete_task → list_achievements 应该能看到 ready 成就."""
    proc, db_path = mcp_server
    from app.core import storage
    from app.core.models import ProjectCreate, TaskCreate

    async def _setup():
        storage.init_engine(database_url=f"sqlite+aiosqlite:///{db_path}")
        await storage.create_tables()
        p = await storage.add_project(ProjectCreate(name="项目"))
        t = await storage.add_task(TaskCreate(project=p.id, title="MCP 任务"))
        return t.id

    task_id = asyncio.run(_setup())

    # mcp complete_task
    resp = _send_request(proc, "tools/call", {
        "name": "complete_task",
        "arguments": {
            "task_id": task_id,
            "outcome": "主导 MCP 集成, 让 Claude Code 能调 cockpit",
            "cv": "主导 cockpit MCP 集成, 暴露 5 个核心工具给 Claude Code / Cursor 调用",
        },
    }, req_id=7)
    assert "result" in resp, f"complete_task failed: {resp}"
    completed = json.loads(resp["result"]["content"][0]["text"])
    assert completed["cv_status"] == "ready"
    assert "MCP 集成" in completed["cv"]

    # mcp list_achievements 验证
    resp = _send_request(proc, "tools/call", {
        "name": "list_achievements",
        "arguments": {"cv_status": "ready"},
    }, req_id=8)
    achs = json.loads(resp["result"]["content"][0]["text"])
    assert len(achs) == 1
    assert "MCP 集成" in achs[0]["cv"]


# ============================================================================
# 5. 完整工作流 (add → complete → list)
# ============================================================================

def test_mcp_end_to_end_workflow(mcp_server):
    """完整 MCP 工作流: 建项目 (直接) → add_task → complete_task → list_achievements."""
    proc, db_path = mcp_server
    from app.core import storage
    from app.core.models import ProjectCreate

    async def _setup():
        storage.init_engine(database_url=f"sqlite+aiosqlite:///{db_path}")
        await storage.create_tables()
        p = await storage.add_project(ProjectCreate(name="端到端项目"))
        return p.id

    project_id = asyncio.run(_setup())

    # 1. add_task via mcp
    add_resp = _send_request(proc, "tools/call", {
        "name": "add_task",
        "arguments": {"project_id": project_id, "title": "写 v0.5a 测试"},
    }, req_id=10)
    task = json.loads(add_resp["result"]["content"][0]["text"])
    assert task["title"] == "写 v0.5a 测试"

    # 2. complete_task via mcp
    complete_resp = _send_request(proc, "tools/call", {
        "name": "complete_task",
        "arguments": {
            "task_id": task["id"],
            "outcome": "写了 MCP server + 6 个测试",
            "cv": "主导 cockpit MCP 集成, 暴露 5 工具, 加端到端测试覆盖",
        },
    }, req_id=11)
    achievement = json.loads(complete_resp["result"]["content"][0]["text"])
    assert achievement["cv_status"] == "ready"

    # 3. list_achievements 验证
    list_resp = _send_request(proc, "tools/call", {
        "name": "list_achievements",
        "arguments": {},
    }, req_id=12)
    achs = json.loads(list_resp["result"]["content"][0]["text"])
    assert len(achs) == 1
    assert achs[0]["cv_status"] == "ready"
    assert achs[0]["title"] == "写 v0.5a 测试"


# ============================================================================
# 6. complete_task 错误路径 — 不存在的 task_id 返 error
# ============================================================================

def test_mcp_complete_task_invalid_id_returns_error(mcp_server):
    """不存在的 task_id 必返 error, 不静默成功."""
    proc, _ = mcp_server
    resp = _send_request(proc, "tools/call", {
        "name": "complete_task",
        "arguments": {
            "task_id": "non_existent_task_99999",
            "outcome": "X",
            "cv": "X",
        },
    }, req_id=13)
    assert "result" in resp, f"call failed: {resp}"
    content = resp["result"]["content"]
    result = json.loads(content[0]["text"])
    # mcp 工具层返 error 字段 (不是 isError, 是 text 里 json 含 error)
    assert "error" in result, f"expected error in result, got {result}"
