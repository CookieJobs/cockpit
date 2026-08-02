"""v0.5a.1 接入中心 API 测试 (2026-08-02 立).

覆盖:
  1. GET /api/integrations/supported — 列出 6 个 agent + 各自配置路径
  2. GET /api/integrations/status — 列出已接入 / 未接入
  3. POST /api/integrations/install — 写 cockpit 段, 保留其他 server
  4. POST /api/integrations/install — 幂等 (重装返回 was_already_installed)
  5. POST /api/integrations/install — 拒绝 command 类型 (WorkBuddy 应走对话命令)
  6. POST /api/integrations/install — 未知 agent_id 返 404
  7. POST /api/integrations/uninstall — 删 cockpit 段, 保留其他 server
  8. POST /api/integrations/uninstall — config 不存在时 graceful
  9. POST /api/integrations/uninstall — cockpit 不在时 graceful
 10. install + uninstall 端到端 (status 联动)

设计: 用 monkeypatch 替换 AGENTS 列表 + 路径, 让测试走临时目录, 不污染用户 home.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import integrations


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


@pytest.fixture
def fake_agents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """把 AGENTS 替换成走 tmp_path 的 3 个测试 agent.

    包含:
      - json_user:    全局级 JSON config (模拟 Claude Code)
      - json_project: 项目级 JSON config (模拟 Trae)
      - command:      command 类型 (模拟 WorkBuddy)
    """
    test_agents: list[dict[str, Any]] = [
        {
            "id": "fake_json_user",
            "name": "Fake JSON User",
            "type": "json",
            "scope": "user",
            "config_paths": {
                "Darwin": str(tmp_path / "json_user.json"),
                "Linux": str(tmp_path / "json_user.json"),
                "Windows": str(tmp_path / "json_user.json"),
            },
            "note": "测试用 json user",
            "docs_url": None,
            "post_install": "重启测试 client",
        },
        {
            "id": "fake_json_project",
            "name": "Fake JSON Project",
            "type": "json",
            "scope": "project",
            "config_paths": {
                "Darwin": str(tmp_path / "json_project.json"),
                "Linux": str(tmp_path / "json_project.json"),
                "Windows": str(tmp_path / "json_project.json"),
            },
            "note": "测试用 json project",
            "docs_url": None,
            "post_install": "重启测试 client",
        },
        {
            "id": "fake_command",
            "name": "Fake Command",
            "type": "command",
            "install_command": "fake command install",
            "manual_command": "在 Fake 对话框输入: fake command install",
            "note": "测试用 command",
            "docs_url": None,
            "post_install": "在 Fake 对话框说 '列 cockpit 项目' 测试",
        },
    ]
    monkeypatch.setattr(integrations, "AGENTS", test_agents)
    return test_agents, tmp_path


# =====================================================================
# 1. supported
# =====================================================================

def test_supported_returns_all_agents(client: TestClient, fake_agents):
    """GET /supported → 返 3 个 agent (我们注入的 3 个) + current_os + cockpit_path."""
    res = client.get("/api/integrations/supported")
    assert res.status_code == 200
    body = res.json()
    assert "cockpit_path" in body
    assert body["current_os"] in ("Darwin", "Linux", "Windows")
    assert len(body["agents"]) == 3

    ids = {a["id"] for a in body["agents"]}
    assert ids == {"fake_json_user", "fake_json_project", "fake_command"}


def test_supported_json_agent_has_config_paths(client: TestClient, fake_agents):
    """json 类型 agent 应该有 current_os_path 字段 (展开后) + config_paths."""
    res = client.get("/api/integrations/supported")
    body = res.json()
    json_user = next(a for a in body["agents"] if a["id"] == "fake_json_user")
    assert json_user["type"] == "json"
    assert json_user["current_os_path"].endswith("json_user.json")
    assert "Darwin" in json_user["config_paths"]


def test_supported_command_agent_has_install_command(client: TestClient, fake_agents):
    """command 类型 agent 应有 install_command 字段, 没有 current_os_path."""
    res = client.get("/api/integrations/supported")
    body = res.json()
    cmd = next(a for a in body["agents"] if a["id"] == "fake_command")
    assert cmd["type"] == "command"
    assert cmd["install_command"] == "fake command install"
    assert cmd.get("current_os_path") is None


def test_supported_not_installed_initially(client: TestClient, fake_agents, tmp_path):
    """全新环境 → 没有任何 agent 接入 (config 文件不存在)."""
    res = client.get("/api/integrations/supported")
    body = res.json()
    for a in body["agents"]:
        assert a["is_installed"] is False, f"{a['id']} 应该是未接入"


# =====================================================================
# 2. status
# =====================================================================

def test_status_empty_initially(client: TestClient, fake_agents):
    """status 在全新环境应该 installed_count=0."""
    res = client.get("/api/integrations/status")
    assert res.status_code == 200
    body = res.json()
    assert body["installed_count"] == 0
    assert body["total_count"] == 3
    assert len(body["installed"]) == 0
    assert len(body["not_installed"]) == 3


# =====================================================================
# 3. install — 写文件 + 保留其他 server
# =====================================================================

def test_install_creates_config_file_with_cockpit_segment(
    client: TestClient, fake_agents, tmp_path
):
    """安装 → config 文件被创建, 包含 mcpServers.cockpit 段, command/args/cwd 正确."""
    res = client.post(
        "/api/integrations/install",
        json={"agent_id": "fake_json_user", "cockpit_path": "/test/cockpit"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["was_already_installed"] is False

    config_path = Path(body["config_path"])
    assert config_path.exists()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert "mcpServers" in cfg
    assert "cockpit" in cfg["mcpServers"]
    segment = cfg["mcpServers"]["cockpit"]
    assert segment["command"] == "python"
    assert segment["args"] == ["-m", "app.mcp_server"]
    assert segment["cwd"] == "/test/cockpit"


def test_install_preserves_other_servers(
    client: TestClient, fake_agents, tmp_path
):
    """安装 cockpit → 已有的其他 MCP server 全部保留, 不覆盖."""
    config_path = tmp_path / "json_user.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "other_server": {
                        "command": "node",
                        "args": ["server.js"],
                    },
                    "another": {"command": "ruby", "args": ["x.rb"]},
                }
            }
        ),
        encoding="utf-8",
    )
    res = client.post(
        "/api/integrations/install",
        json={"agent_id": "fake_json_user"},
    )
    assert res.status_code == 200
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert "cockpit" in cfg["mcpServers"]
    assert cfg["mcpServers"]["other_server"] == {
        "command": "node",
        "args": ["server.js"],
    }
    assert cfg["mcpServers"]["another"] == {"command": "ruby", "args": ["x.rb"]}


def test_install_uses_default_cockpit_path_when_omitted(
    client: TestClient, fake_agents, tmp_path
):
    """不传 cockpit_path → 走 _detect_cockpit_path() 默认值 (cwd)."""
    res = client.post(
        "/api/integrations/install",
        json={"agent_id": "fake_json_user"},
    )
    assert res.status_code == 200
    cfg = json.loads((tmp_path / "json_user.json").read_text(encoding="utf-8"))
    cwd_in_segment = cfg["mcpServers"]["cockpit"]["cwd"]
    # 默认应该是 os.getcwd(), 不应该是 None / 空
    assert cwd_in_segment
    assert len(cwd_in_segment) > 0


# =====================================================================
# 4. install — 幂等 + 拒绝 command + 404
# =====================================================================

def test_install_is_idempotent(client: TestClient, fake_agents, tmp_path):
    """重装同一 agent → was_already_installed=True, 文件内容不变 (不重复 segment)."""
    client.post("/api/integrations/install", json={"agent_id": "fake_json_user"})
    res2 = client.post("/api/integrations/install", json={"agent_id": "fake_json_user"})
    assert res2.status_code == 200
    assert res2.json()["was_already_installed"] is True
    cfg = json.loads((tmp_path / "json_user.json").read_text(encoding="utf-8"))
    assert len(cfg["mcpServers"]) == 1
    assert "cockpit" in cfg["mcpServers"]


def test_install_rejects_command_type(client: TestClient, fake_agents):
    """WorkBuddy 这种 command 类型应该 400, 引导用户用 install_command."""
    res = client.post(
        "/api/integrations/install",
        json={"agent_id": "fake_command"},
    )
    assert res.status_code == 400
    assert "install_command" in res.text or "JSON" in res.text


def test_install_unknown_agent_returns_404(client: TestClient, fake_agents):
    """未知 agent_id → 404."""
    res = client.post(
        "/api/integrations/install",
        json={"agent_id": "not_an_agent"},
    )
    assert res.status_code == 404


# =====================================================================
# 5. uninstall
# =====================================================================

def test_uninstall_removes_cockpit_segment_preserves_others(
    client: TestClient, fake_agents, tmp_path
):
    """卸载 → cockpit 段被删, 其他 server 保留."""
    # 先建一个含 cockpit + other_server 的 config
    config_path = tmp_path / "json_user.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "cockpit": {
                        "command": "python",
                        "args": ["-m", "app.mcp_server"],
                        "cwd": "/x",
                    },
                    "other": {"command": "node", "args": ["y.js"]},
                }
            }
        ),
        encoding="utf-8",
    )
    res = client.post(
        "/api/integrations/uninstall",
        json={"agent_id": "fake_json_user"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["removed"] is True
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert "cockpit" not in cfg["mcpServers"]
    assert cfg["mcpServers"]["other"] == {"command": "node", "args": ["y.js"]}


def test_uninstall_cleans_empty_mcpservers_key(
    client: TestClient, fake_agents, tmp_path
):
    """卸载后 mcpServers 为空 → 整段删掉 (不留空对象)."""
    config_path = tmp_path / "json_user.json"
    config_path.write_text(
        json.dumps(
            {"mcpServers": {"cockpit": {"command": "python", "args": ["-m", "app.mcp_server"], "cwd": "/x"}}}
        ),
        encoding="utf-8",
    )
    res = client.post(
        "/api/integrations/uninstall",
        json={"agent_id": "fake_json_user"},
    )
    assert res.status_code == 200
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    assert "mcpServers" not in cfg
    assert cfg == {}  # 应该清空 (除了 mcpServers 没其他字段)


def test_uninstall_config_not_exists_is_graceful(
    client: TestClient, fake_agents, tmp_path
):
    """config 文件不存在 → 返 success=True, removed=False, 不报错."""
    res = client.post(
        "/api/integrations/uninstall",
        json={"agent_id": "fake_json_user"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["removed"] is False


def test_uninstall_cockpit_not_in_config_is_graceful(
    client: TestClient, fake_agents, tmp_path
):
    """config 存在但 cockpit 不在里面 → graceful skip."""
    config_path = tmp_path / "json_user.json"
    config_path.write_text(
        json.dumps({"mcpServers": {"other": {"command": "x", "args": []}}}),
        encoding="utf-8",
    )
    res = client.post(
        "/api/integrations/uninstall",
        json={"agent_id": "fake_json_user"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["removed"] is False


def test_uninstall_rejects_command_type(client: TestClient, fake_agents):
    """command 类型不通过 uninstall 走 (它本来就没装)."""
    res = client.post(
        "/api/integrations/uninstall",
        json={"agent_id": "fake_command"},
    )
    assert res.status_code == 400


# =====================================================================
# 6. 端到端: install → status 变化 → uninstall → status 回到 0
# =====================================================================

def test_install_status_uninstall_e2e(
    client: TestClient, fake_agents, tmp_path
):
    """完整链路: 安装后 status 反映, 卸载后回到 0."""
    # 1. 初始 — 未接入
    s0 = client.get("/api/integrations/status").json()
    assert s0["installed_count"] == 0

    # 2. 安装
    r_install = client.post(
        "/api/integrations/install",
        json={"agent_id": "fake_json_user"},
    )
    assert r_install.status_code == 200

    # 3. status 应该反映
    s1 = client.get("/api/integrations/status").json()
    assert s1["installed_count"] == 1
    installed_ids = {a["id"] for a in s1["installed"]}
    assert "fake_json_user" in installed_ids

    # 4. supported.is_installed 也应该 True
    sup = client.get("/api/integrations/supported").json()
    user_agent = next(a for a in sup["agents"] if a["id"] == "fake_json_user")
    assert user_agent["is_installed"] is True

    # 5. 卸载
    r_uninstall = client.post(
        "/api/integrations/uninstall",
        json={"agent_id": "fake_json_user"},
    )
    assert r_uninstall.status_code == 200

    # 6. status 回到 0
    s2 = client.get("/api/integrations/status").json()
    assert s2["installed_count"] == 0
