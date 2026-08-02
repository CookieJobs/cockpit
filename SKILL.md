# Cockpit MCP Server

让 Claude Code / Cursor / 其他 MCP 客户端能调 cockpit 的工作流管理工具。

## 安装（推荐方式：cockpit 接入中心）

打开 cockpit web → 顶栏 **🔌 集成** → 6 个 agent 卡片（Claude Code / Cursor / Trae / Cline / Continue / WorkBuddy）→ 点 [一键安装]。

不用手改 JSON，不用找路径，不用纠结 Trae 项目级 vs Claude Code 全局。

支持：
- **json 类型**（Claude Code / Cursor / Trae / Cline / Continue）：后端读现有 config → 只改 `mcpServers.cockpit` 段 → 写回（**保留所有其他 server**）。
- **command 类型**（WorkBuddy）：后端不写 config，返对话命令 `workbuddy mcp install cockpit`，你复制粘贴到 WorkBuddy 对话框。

界面长这样：

```
┌──────────────────────────────────────────────┐
│ Claude Code    [已接入]  [卸载]              │
│ ~/.claude/mcp.json                           │
│ 重启 Claude Code 即可生效                     │
├──────────────────────────────────────────────┤
│ WorkBuddy      [待手动]  [复制安装命令] [详细]│
│ 在 WorkBuddy 对话框输入:                     │
│   workbuddy mcp install cockpit              │
└──────────────────────────────────────────────┘
```

## 安装（手动方式：直接改 JSON）

如果不想用接入中心（CI/部署/无 cockpit web），手动配置也支持：

### Claude Code

在 `~/.claude/mcp.json` 或项目根 `.mcp.json` 加：

```json
{
  "mcpServers": {
    "cockpit": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/Users/liujin/Documents/cockpit",
      "env": {
        "COCKPIT_DATABASE_URL": "sqlite+aiosqlite:////Users/<you>/.cockpit/cockpit.db"
      }
    }
  }
}
```

**重要**：把 `cwd` 跟 `COCKPIT_DATABASE_URL` 改成你的实际路径。

### Cursor

在 `~/.cursor/mcp.json` 同理。

### Codex / Dify / OpenClaw

每个客户端的 mcp config 格式略不同，但本质都是 "command + args + cwd + env"。

## 5 个核心工具

| 工具 | 用途 | 必填参数 |
|---|---|---|
| `list_projects` | 列所有项目（拿 project ID）| — |
| `list_tasks` | 列任务（拿 task ID）| project_id? |
| `add_task` | 新建任务 | project_id, title |
| `complete_task` | 完成任务 + 沉淀成就 | task_id, outcome, cv |
| `list_achievements` | 列成就（看沉淀）| cv_status?, since? |

## 工作流示例

**场景**：让 Claude Code 在你写完代码后自动建任务 + 沉淀成就。

```
1. Claude Code 调 list_projects → 找到 "我的项目" 的 ID
2. Claude Code 调 add_task(project_id, title="修登录 bug", priority="P1")
3. 你完成代码后, Claude Code 调 complete_task(
     task_id, outcome="修了登录鉴权 bug",
     cv="定位并修复登录鉴权高优先级 bug, DAU 提升 5%"
   )
4. 成就自动入库 cv_status=ready
5. 下次写周报, Claude Code 调 list_achievements(cv_status="ready", since="2026-08-01")
   → 拉出你过去的所有 ready 成就
6. Claude Code 用这些素材写周报
```

## 提示

- `cv` 字段应该是"简历级成就陈述"：用「主导/设计/重构」等强动词开头，尽量含量化数据
- `cv_status` 默认 `ready`；内容有缺口用 `needs_data`（差数据）或 `pending`（草稿）
- `outcome` 必填（哪怕只写"做完了"），`cv` 由 AI 润色 outcome 生成
- `list_achievements` 不带 `cv_status` 返全量

## 协议

- **stdio transport**（默认）：MCP 客户端启动 cockpit 作为子进程
- **JSON-RPC 2.0** + line-delimited JSON（mcp 2.0 标准）
- mcp SDK: 2.0.0+

## 测试

```bash
cd /Users/liujin/Documents/cockpit
.venv/bin/pytest app/tests/test_mcp_server.py -v
# 7 passed
```

## 已知限制

- `add_task` 需要 `project_id`（先调 `list_projects` 拿）— v0.5b 计划加 `create_project` 工具
- `complete_task` 不调 LLM 润色 cv（要求 AI 自己润）— 跟 cockpit 内部 complete 行为不同
- 一次只返最多 N 条（list 默认 100，list_achievements 返全量）

## 跟 cockpit 本身的关系

MCP server 跟 web 共享同一个 SQLite db（`~/.cockpit/cockpit.db`）。
- 你在 cockpit web 完成的任务 → 立刻在 MCP 里能看到
- Claude Code 通过 MCP 沉淀的成就 → 立刻在 cockpit web 的成就库里看到
- **双向实时同步**

## Roadmap

- v0.5b: Git 集成（commit → 任务草稿）
- v0.6: 智能提炼（agent 主动识别可沉淀的成就）
- v0.7: 统一输出引擎（多模板 + LLM 润色）— 让 MCP 端也能调
