"""对话 cmd_complete 路径测试 (2026-08-23 立)。

背景:
- 之前 cmd_complete 调 storage.complete_task(... cv_status=READY, outcome=""),
  被后端静默降级到 needs_data, 但聊天返回文案说"已沉淀进成就库" — 误导
- 2026-08-23 修: 显式传 cv_status=PENDING + 文案改成"已存为草稿"

锁住 2 件事:
1. cmd_complete 必须显式传 PENDING, 不能 READY (后端会强制降级但文案会失真)
2. 聊天返回文案必须如实说"草稿/待补", 不能误导成"已沉淀"
"""
import pytest

from app.core import chat, storage
from app.core.models import ProjectCreate, TaskCreate


@pytest.mark.asyncio
async def test_cmd_complete_saves_as_pending_draft(temp_db):
    """对话路径"X 完成了"必须存草稿, 不允许前端走捷径到 ready/needs_data。"""
    project = await storage.add_project(ProjectCreate(name="对话路径"))
    task = await storage.add_task(TaskCreate(project=project.id, title="写一份上线复盘"))

    response = await chat.cmd_complete("写一份上线复盘完成了")

    # 1. 响应必须明确说"草稿/待补" — 防止以后有人改回"已沉淀进成就库"误导文案
    assert "草稿" in response.text or "待补" in response.text, (
        f"cmd_complete 文案必须说草稿/待补, 不能误导成'已沉淀'。实际: {response.text!r}"
    )
    assert "已沉淀进成就库" not in response.text, (
        "cmd_complete 文案不能再说'已沉淀进成就库' — 对话路径无 outcome "
        "= 用户选了暂存, 不是已就绪"
    )

    # 2. action 必须是 task_completed (跟之前一致), data 里有 achievement
    assert response.action == "task_completed"
    achievement = response.data["achievement"]
    assert achievement is not None

    # 3. achievement 必须是 pending 状态 (不是 ready/needs_data)
    assert achievement["cv_status"] == "pending", (
        f"cmd_complete 入库必须是 pending, 实际: {achievement['cv_status']!r} — "
        f"对话路径没有 outcome, 走捷径到 ready 会绕过质量门"
    )

    # 4. task 应标记已完成 (草稿不阻塞完成动作本身)
    task_after = await storage.get_task(task.id)
    assert task_after.status.value == "已完成", (
        f"task.status 应是已完成, 实际: {task_after.status!r}"
    )


@pytest.mark.asyncio
async def test_cmd_complete_ambiguous_keyword_returns_help(temp_db):
    """对话路径触发词不清 (只有「完成了」无任务关键词) 必须给提示, 不入库。"""
    response = await chat.cmd_complete("完成了")
    assert "用法" in response.text or "💡" in response.text
    assert response.action is None or response.action != "task_completed"


@pytest.mark.asyncio
async def test_cmd_complete_no_matching_task_returns_error(temp_db):
    """对话路径找不到匹配任务必须给友好错误, 不入库。"""
    project = await storage.add_project(ProjectCreate(name="X"))
    await storage.add_task(TaskCreate(project=project.id, title="写季度汇报"))

    response = await chat.cmd_complete("根本不存在的任务完成了")
    assert "没找到" in response.text
    assert response.data is None or response.data.get("achievement") is None