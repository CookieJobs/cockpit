"""Cockpit 接入中心 API (v0.5a.1 立, 2026-08-02).

让用户**一键**把 cockpit MCP server 注册到 Claude Code / Cursor / Trae / Cline / Continue / WorkBuddy
等 agent / IDE. 不用手改 JSON 找路径.

设计:
  - 4 个端点: supported / install / uninstall / status
  - 不破坏现有 config (读 + 改 mcpServers.cockpit 段, 其他 server 保留)
  - 跨平台路径 (darwin/linux/win32)
  - WorkBuddy 不写 config, 返对话命令让用户复制
"""
import json
import logging
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


# ============================================================================
# Agent metadata: 每个 agent 的 config 路径 / 配置方式
# ============================================================================

def _expand(path_template: str) -> str:
    """展开 ~ / 环境变量 (用于 config path)."""
    return os.path.expanduser(os.path.expandvars(path_template))


def _detect_cockpit_path() -> str:
    """cockpit 安装路径: 环境变量 → cwd 兜底."""
    return os.environ.get("COCKPIT_INSTALL_PATH") or os.getcwd()


def _build_cockpit_mcp_config(cockpit_path: Optional[str] = None) -> dict[str, Any]:
    """生成 cockpit MCP server 段 (写入各 agent mcpServers.cockpit)."""
    path = cockpit_path or _detect_cockpit_path()
    return {
        "command": "python",
        "args": ["-m", "app.mcp_server"],
        "cwd": path,
    }


# Agent 注册表
# type: "json" = 写 JSON config 文件
# type: "command" = 不写 config, 返 install_command 让用户复制
AGENTS: list[dict[str, Any]] = [
    {
        "id": "claude_code",
        "name": "Claude Code",
        "type": "json",
        "scope": "user",  # user-level (全机器)
        "config_paths": {
            "Darwin": "~/.claude/mcp.json",
            "Linux": "~/.claude/mcp.json",
            "Windows": "%USERPROFILE%\\.claude\\mcp.json",
        },
        "note": "Anthropic 官方 CLI. 全局配置, 影响所有项目.",
        "docs_url": "https://docs.anthropic.com/en/docs/claude-code/mcp",
        "post_install": "重启 Claude Code 即可生效 (命令行 / IDE 客户端都算).",
    },
    {
        "id": "cursor",
        "name": "Cursor",
        "type": "json",
        "scope": "user",
        "config_paths": {
            "Darwin": "~/.cursor/mcp.json",
            "Linux": "~/.cursor/mcp.json",
            "Windows": "%USERPROFILE%\\.cursor\\mcp.json",
        },
        "note": "Cursor 全局配置. 项目级也可以在 .cursor/mcp.json.",
        "docs_url": "https://docs.cursor.com/context/model-context-protocol",
        "post_install": "Cursor → Settings → MCP → Refresh, 看到 'cockpit' 即可.",
    },
    {
        "id": "trae",
        "name": "Trae (项目级)",
        "type": "json",
        "scope": "project",  # ⚠️ Trae 只支持项目级
        "config_paths": {
            "Darwin": ".trae/mcp.json",
            "Linux": ".trae/mcp.json",
            "Windows": ".trae\\mcp.json",
        },
        "note": "Trae 只支持项目级 (无 user-level). 必须在 cockpit 项目根目录跑.",
        "docs_url": "https://docs.trae.cn/",
        "post_install": "Trae 自动检测, 重启 AI 侧栏或重启 IDE.",
    },
    {
        "id": "cline",
        "name": "Cline (VSCode)",
        "type": "json",
        "scope": "user",
        "config_paths": {
            "Darwin": "~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            "Linux": "~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            "Windows": "%APPDATA%\\Code\\User\\globalStorage\\saoudrizwan.claude-dev\\settings\\cline_mcp_settings.json",
        },
        "note": "VSCode 插件 Cline. 路径长, 是手改最容易出错的.",
        "post_install": "VSCode → Cline 面板 → 应该自动出现 cockpit 工具.",
    },
    {
        "id": "continue",
        "name": "Continue (VSCode / JetBrains)",
        "type": "json",
        "scope": "user",
        "config_paths": {
            "Darwin": "~/.continue/config.json",
            "Linux": "~/.continue/config.json",
            "Windows": "%USERPROFILE%\\.continue\\config.json",
        },
        "note": "Continue Dev (开源). config 跟 mcpServers 略不同, 自动适配.",
        "post_install": "VSCode → Continue 面板 → 模型下拉 → 工具 → 应该看到 cockpit.",
    },
    {
        "id": "workbuddy",
        "name": "WorkBuddy",
        "type": "command",  # ⚠️ WorkBuddy 不写 JSON, 走对话命令
        "install_command": "workbuddy mcp install cockpit",  # 用户在 WorkBuddy 对话框输入
        "manual_command": (
            "在 WorkBuddy 对话框输入：\n\n"
            "  workbuddy mcp install cockpit\n\n"
            "然后填入:\n"
            "  command: python\n"
            "  args: -m app.mcp_server\n"
            "  cwd: <cockpit 安装路径>"
        ),
        "note": "WorkBuddy 不写 JSON, 走对话命令安装 (WorkBuddy 体验最好的部分).",
        "docs_url": "https://www.codebuddy.cn/work/",
        "post_install": "WorkBuddy 对话说 '列 cockpit 项目' 测试.",
    },
]


# ============================================================================
# 端点 1: GET /api/integrations/supported — 列出所有支持的 agent
# ============================================================================

@router.get("/supported")
async def list_supported_agents() -> dict[str, Any]:
    """列出支持的 agent + 当前 OS + 各 agent 配置路径 + 已接入状态."""
    os_name = platform.system()
    cockpit_path = _detect_cockpit_path()
    results = []
    for agent in AGENTS:
        item = {
            "id": agent["id"],
            "name": agent["name"],
            "type": agent["type"],
            "scope": agent.get("scope"),
            "note": agent["note"],
            "docs_url": agent.get("docs_url"),
            "post_install": agent["post_install"],
        }
        if agent["type"] == "json":
            # 跨平台 config 路径
            item["config_paths"] = {
                k: _expand(v) for k, v in agent["config_paths"].items()
            }
            # 当前 OS 的实际路径
            current_path = agent["config_paths"].get(os_name)
            if current_path:
                item["current_os_path"] = _expand(current_path)
                item["is_installed"] = _is_already_installed(_expand(current_path), cockpit_path)
            else:
                item["current_os_path"] = None
                item["is_installed"] = False
        else:  # command 类型
            item["install_command"] = agent["install_command"]
            item["manual_command"] = agent["manual_command"]
            # WorkBuddy 不写 config, "已接入" 不能用文件判断
            # 留个 stub 让前端能显示状态 (未来可加 WorkBuddy 端点检查)
            item["is_installed"] = False
        results.append(item)
    return {
        "cockpit_path": cockpit_path,
        "current_os": os_name,
        "agents": results,
    }


def _is_already_installed(config_path: str, cockpit_path: str) -> bool:
    """读 config 文件, 检查 mcpServers.cockpit.cwd 是否匹配当前 cockpit 路径."""
    p = Path(config_path)
    if not p.exists():
        return False
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
        server = cfg.get("mcpServers", {}).get("cockpit")
        if not server:
            return False
        # 简单判断: cwd 路径匹配 (兼容绝对/相对)
        return server.get("cwd", "").rstrip("/") == cockpit_path.rstrip("/")
    except (json.JSONDecodeError, OSError):
        return False


# ============================================================================
# 端点 2: POST /api/integrations/install — 写 config
# ============================================================================

class InstallRequest(BaseModel):
    agent_id: str = Field(..., description="agent id (e.g. claude_code)")
    cockpit_path: Optional[str] = Field(None, description="cockpit 安装路径 (默认自动检测)")


@router.post("/install")
async def install_agent(req: InstallRequest) -> dict[str, Any]:
    """把 cockpit MCP server 写到指定 agent 的 config 文件.

    关键设计:
      - 读现有 config → 不覆盖其他 server
      - 只改 mcpServers.cockpit 段
      - 用临时文件 + rename 防半写状态
      - 自动创建父目录
    """
    agent = _find_agent(req.agent_id)
    if agent["type"] != "json":
        raise HTTPException(400, f"agent {req.agent_id} 不走 JSON config, 请用 'install_command'")

    os_name = platform.system()
    path_template = agent["config_paths"].get(os_name)
    if not path_template:
        raise HTTPException(400, f"OS {os_name} 不支持 agent {req.agent_id}")

    config_path = Path(_expand(path_template))
    cockpit_path = req.cockpit_path or _detect_cockpit_path()
    cockpit_segment = _build_cockpit_mcp_config(cockpit_path)

    # 读现有 config (不覆盖)
    existing: dict[str, Any] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, OSError):
            logger.warning(f"config {config_path} 解析失败, 当空对象处理")
            existing = {}

    # 更新 mcpServers.cockpit 段
    servers = existing.setdefault("mcpServers", {})
    was_already = "cockpit" in servers
    servers["cockpit"] = cockpit_segment

    # 写回 (临时文件 + rename, 避免半写状态)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, prefix=".cockpit-mcp-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, config_path)
    except Exception:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    logger.info(f"cockpit MCP installed to {agent['id']} at {config_path}")
    return {
        "success": True,
        "agent_id": req.agent_id,
        "config_path": str(config_path),
        "was_already_installed": was_already,
        "post_install": agent["post_install"],
    }


# ============================================================================
# 端点 3: POST /api/integrations/uninstall — 删 config 段
# ============================================================================

class UninstallRequest(BaseModel):
    agent_id: str


@router.post("/uninstall")
async def uninstall_agent(req: UninstallRequest) -> dict[str, Any]:
    """从 agent config 删 cockpit 段 (其他 server 保留)."""
    agent = _find_agent(req.agent_id)
    if agent["type"] != "json":
        raise HTTPException(400, f"agent {req.agent_id} 不走 JSON config")

    os_name = platform.system()
    path_template = agent["config_paths"].get(os_name)
    if not path_template:
        raise HTTPException(400, f"OS {os_name} 不支持 agent {req.agent_id}")

    config_path = Path(_expand(path_template))
    if not config_path.exists():
        return {
            "success": True,
            "agent_id": req.agent_id,
            "removed": False,
            "note": "config 文件不存在, 跳过",
        }

    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise HTTPException(500, f"config 解析失败: {config_path}")

    servers = cfg.get("mcpServers", {})
    if "cockpit" not in servers:
        return {
            "success": True,
            "agent_id": req.agent_id,
            "removed": False,
            "note": "cockpit 不在 mcpServers 中, 跳过",
        }

    del servers["cockpit"]
    # 如果 mcpServers 空, 删整段
    if not servers:
        cfg.pop("mcpServers", None)

    # 写回
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, prefix=".cockpit-mcp-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, config_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return {
        "success": True,
        "agent_id": req.agent_id,
        "removed": True,
        "config_path": str(config_path),
    }


# ============================================================================
# 端点 4: GET /api/integrations/status — 检查 cockpit 在哪些 agent 已接入
# ============================================================================

@router.get("/status")
async def integration_status() -> dict[str, Any]:
    """快速查 cockpit 当前已接入哪些 agent (前端 nav 显示用)."""
    os_name = platform.system()
    cockpit_path = _detect_cockpit_path()
    installed = []
    not_installed = []
    for agent in AGENTS:
        item = {
            "id": agent["id"],
            "name": agent["name"],
            "type": agent["type"],
        }
        if agent["type"] == "json":
            path_template = agent["config_paths"].get(os_name)
            if path_template:
                expanded = _expand(path_template)
                is_inst = _is_already_installed(expanded, cockpit_path)
                item["config_path"] = expanded
                item["is_installed"] = is_inst
                (installed if is_inst else not_installed).append(item)
            else:
                item["is_installed"] = False
                not_installed.append(item)
        else:
            # command 类型无法自动检测, 暂未接入
            item["is_installed"] = False
            not_installed.append(item)
    return {
        "cockpit_path": cockpit_path,
        "current_os": os_name,
        "installed_count": len(installed),
        "total_count": len(AGENTS),
        "installed": installed,
        "not_installed": not_installed,
    }


# ============================================================================
# 工具
# ============================================================================

def _find_agent(agent_id: str) -> dict[str, Any]:
    for a in AGENTS:
        if a["id"] == agent_id:
            return a
    raise HTTPException(404, f"Unknown agent: {agent_id}")
