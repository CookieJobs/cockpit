#!/usr/bin/env python
"""Cockpit 演示数据播种脚本（2026-07-20 立）。

故事线: 一个产品经理用 Cockpit 管自己的 dogfooding, 体现这次 6 项新特性:

- cvStatus 三态 (ready / needs_data / pending): 7 条 ready + 2 条 needs_data + 1 条 pending
- 项目归档: 1 个已归档项目 (Landing Page 重构)
- /today 晨间 ritual: 5 个 focus (高/中/低 都有, 含 1 个 blocked, 1 个 due 今天)
- /report workspace: 跨本周/上周/本月的成就, 覆盖 3 个模板的输入数据
- ChatWindow 重构: 无演示 (内部重构, 行为不变)
- AGENTS.md 拆 lessons: 无演示 (文档)

设计原则:
- 幂等: 每次跑会先清空再插, 不留垃圾
- 真实: 用的都是 cockpit 自身 dogfooding 的真实场景 (修 bug / 写 PRD / 1v1)
- 易于观察: 每条数据都有清晰的特征, 走到哪个页面都能直接看到效果

跑法:
  source .venv/bin/activate
  python scripts/seed_demo.py                    # 用默认 confirm 提示
  python scripts/seed_demo.py --force            # 跳过确认
  python scripts/seed_demo.py --dry-run          # 只打印不写

危险:
- 会**清空当前 cockpit.db** 里的所有项目/任务/成就/聊天 session
- 不动 LLM 设置 (settings 表里的 llm_config 保留)
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# 把项目根加进 sys.path, 这样能 `from app.core import storage`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core import storage  # noqa: E402
from app.core.models import (  # noqa: E402
    AchievementCreate,
    CVStatus,
    ProjectCreate,
    Priority,
    TaskCreate,
    TaskStatus,
)


# ===== 演示数据 =====

TODAY = date.today()

# 算出"本周一"和"上周一"等日期, 让 report workspace 的时间范围有真实效果
THIS_MONDAY = TODAY - timedelta(days=(TODAY.weekday()))
LAST_MONDAY = THIS_MONDAY - timedelta(days=7)
MONTH_START = TODAY.replace(day=1)


PROJECTS = [
    {
        "name": "Cockpit 自身",
        "description": "Cockpit v0.2 MVP 迭代, 借鉴 task-cockpit 加 UX 改造, 修各类 UX bug",
        "archived": False,
    },
    {
        "name": "Q3 商业化",
        "description": "Q3 述职 + 订阅模式 + 第一批外部用户 dogfooding",
        "archived": False,
    },
    {
        "name": "小红书副业",
        "description": "周更 2 篇, 主题围绕产品经理工具 + 个人成长",
        "archived": False,
    },
    {
        "name": "读书清单 2026",
        "description": "今年读完 12 本, 当前在读《组织行为学》",
        "archived": False,
    },
    {
        "name": "旧版 Landing Page 重构",
        "description": "2026-04 完成, 已经稳定运行 2 个月, 不再需要日常关注",
        "archived": True,  # 这个用来演示归档 UI
    },
]


# 当前活跃任务（用于 /today focus 5 演示）
# 5 个任务 + 1 个 blocked 任务 = 6 总, focus 排序后前 5 含 blocked 那条
TODAY_TASKS = [
    {
        "project": "Cockpit 自身",
        "title": "修登录鉴权 bug",
        "priority": Priority.HIGH,
        "due": TODAY,  # 今天 due, 演示 warning 颜色
        "status": TaskStatus.IN_PROGRESS,
    },
    {
        "project": "Q3 商业化",
        "title": "写完 Q3 述职草稿",
        "priority": Priority.HIGH,
        "due": TODAY + timedelta(days=1),  # 明天 due
        "status": TaskStatus.NOT_STARTED,
    },
    {
        "project": "Cockpit 自身",
        "title": "跟设计对一遍新 dashboard 配色",
        "priority": Priority.MEDIUM,
        "due": TODAY + timedelta(days=3),
        "blocked": True,  # blocked, 演示 focus 里有黄色提示
        "status": TaskStatus.NOT_STARTED,
    },
    {
        "project": "Cockpit 自身",
        "title": "重构 ChatWindow 流式状态机",
        "priority": Priority.MEDIUM,
        "status": TaskStatus.NOT_STARTED,
    },
    {
        "project": "小红书副业",
        "title": "周末写小红书选题",
        "priority": Priority.LOW,
        "due": TODAY + timedelta(days=2),
        "status": TaskStatus.NOT_STARTED,
    },
]


# 演示成就（混合 cv_status 三态 + 跨多个时间范围）
# date_hint 选值:
#   "ago_d{n}"  → N 天前 (不区分周/月, 运行时计算成具体 date)
# 这样不论今天是周几, 数据都在过去, /report 的"本周/上周/本月"三个
# 范围都能按时间分布拿到数据
# (project_name, title, outcome, cv, reflection, cv_status, days_ago)
def _date_for_hint(hint: str) -> date:
    """hint → 具体 date 对象。运行时计算, 适配任何 today。"""
    if hint.startswith("ago_d"):
        d = int(hint.split("d")[1])
        return TODAY - timedelta(days=d)
    raise ValueError(f"Unknown date hint: {hint}")


ACHIEVEMENTS = [
    # ===== 本周 ready (5 条, 演示产品周报主输入) =====
    (
        "Cockpit 自身",
        "修复 chat stream chunk 顺序错乱",
        "DeepSeek 偶发 chunk 顺序错乱, 加了 buffer 重组逻辑",
        "修复 chat stream chunk 顺序错乱问题, 加 buffer 重组逻辑, 偶发卡顿率从 5% 降到 <0.1%",
        "",
        CVStatus.READY,
        "ago_d1",  # 本周第 4 天 (通常是周四, 视今天而定)
    ),
    (
        "Cockpit 自身",
        "4 字段完成 modal 替掉凑数 cv",
        "之前 complete 按钮走默认 cv='完成「XXX」', 没意义; 改成 outcome/cv/reflection/cvStatus 4 字段沉淀",
        "把'完成'按钮从凑数 cv 改成 4 字段沉淀 modal (outcome/cv/reflection/cvStatus), 简历级成就可入率从 30% 提到 90%",
        "复盘: 凑数 cv 是反成就库设计的, 4 字段强约束产出质量",
        CVStatus.READY,
        "ago_d2",
    ),
    (
        "Cockpit 自身",
        "借鉴 task-cockpit 加 8 项 UX 改造",
        "对齐 task-cockpit 的 focus 5 / taskAge / projectEmoji / done_today 等视觉",
        "对齐 task-cockpit 加 8 项 UX 改造 (focus 排序 / 任务挂起天数 / 项目 emoji / 今天已完成折叠等), 看板信息密度提升 ~40%",
        "",
        CVStatus.READY,
        "ago_d3",
    ),
    (
        "Q3 商业化",
        "跟老板 1v1 确认 Q3 述职时间线",
        "敲定 Q3 述职在 9/25 之前, 准备期留 2 周",
        "跟老板 1v1 敲定 Q3 述职时间线 (9/25 前完成), 准备期 2 周, 同步在日历置顶",
        "",
        CVStatus.READY,
        "ago_d0",  # 本周一, 一定在 done_today 范围外 (除非周一)
    ),
    (
        "小红书副业",
        "写完 2 篇小红书",
        "一篇工具推荐 (Notion AI 替代品), 一篇个人成长 (3 年产品经理的复盘)",
        "本周完成 2 篇小红书: 工具推荐 1 篇 (Notion AI 替代品) + 个人成长 1 篇 (3 年产品经理复盘), 平均阅读 2.3k",
        "",
        CVStatus.READY,
        "ago_d0",
    ),
    # ===== 本周 needs_data (3 条, 演示新状态) =====
    (
        "Cockpit 自身",
        "完成 user_profile onboarding 简版",
        "加了 profile 收集 + 引导, 但具体数据没记",
        "上线 user_profile onboarding 简版, 提升首次使用体验",
        "具体留存数字待补, 知道上线后次日留存涨了但没截图",
        CVStatus.NEEDS_DATA,
        "ago_d0",
    ),
    (
        "Q3 商业化",
        "邀请 5 个目标用户 dogfooding",
        "邀请了 5 个朋友试用, 收集反馈",
        "邀请 5 个目标用户 (产品/运营/技术) 试用 Cockpit, 收集 12 条反馈",
        "具体付费意愿数据待补, 5 人里 3 个说愿意付 ¥19/月, 但没问卷佐证",
        CVStatus.NEEDS_DATA,
        "ago_d0",
    ),
    (
        "小红书副业",
        "粉丝破千, 接了第一单商务合作",
        "品牌方来问广告植入, 接了第一单",
        "小红书粉丝破千, 接了第一单商务合作 (¥1500 一篇)",
        "曝光 / 转化数字还没拿到, 复盘要等数据",
        CVStatus.NEEDS_DATA,
        "ago_d2",
    ),
    # ===== 本周 pending (2 条, 演示未写完) =====
    (
        "Cockpit 自身",
        "整理 2026 Q2 复盘",
        "当时没写完, 拖到本周想起来",
        "",
        "",
        CVStatus.PENDING,
        "ago_d3",
    ),
    (
        "Q3 商业化",
        "写 9 月 OKR 初稿",
        "周三开了 OKR 讨论会, 当时记了点子但没整理",
        "",
        "",
        CVStatus.PENDING,
        "ago_d4",
    ),
    # ===== 上周 needs_data (1 条, 演示跨周升级路径) =====
    (
        "Cockpit 自身",
        "加 chat 流式打字机光标",
        "DeepSeek 流式时看不到当前生成位置, 体验差",
        "在 ChatWindow 加打字机光标动画 (流式时跳动的 ▍), 用户知道 AI 正在生成",
        "用户停留时间数据待补, 体感上反馈更顺了但没量化",
        CVStatus.NEEDS_DATA,
        "ago_d8",
    ),
    # ===== 上周 ready (4 条, 演示 /report 上周范围) =====
    (
        "Cockpit 自身",
        "修复 CoT 暴露 + markdown fallback 误执行风险",
        "DeepSeek R1 / MiniMax M3 写 <think> 块, markdown fallback 会当真工具调用",
        "在 chat_engine 入口剥 CoT, markdown fallback 加白名单, 防推理模型在思维链里写伪工具调用被执行",
        "教训: 后端必须在响应入口剥 CoT, 不能让任何下游路径拿到",
        CVStatus.READY,
        "ago_d10",
    ),
    (
        "Cockpit 自身",
        "修复 TaskRow 状态机堵死完成路径",
        "用户报'现在不能通过手动操作完成任务了', 根因是状态机循环 + 整行 click 撞了",
        "修复状态机堵死完成路径: linear (未开始 → 进行中 → 完成 modal), 整行 click 改 onRequestComplete, 加不变量测试锁住",
        "教训: 抄代码必须核对每个分支触发条件, 不要假设上下文'已经存在'",
        CVStatus.READY,
        "ago_d9",
    ),
    (
        "Cockpit 自身",
        "写 PRD v0.2",
        "产品方向定稿, 写完整 PRD",
        "完成 PRD v0.2 (12 节, 含场景 1-5 + MoSCoW + 12 周 roadmap), 跟老板过完确认方向",
        "",
        CVStatus.READY,
        "ago_d8",
    ),
    (
        "Q3 商业化",
        "跟 3 个产品经理朋友聊 dogfooding 体验",
        "聊下来发现'完成即沉淀'是大家最认可的护城河",
        "跟 3 个 3-5 年产品经理聊 dogfooding, 反馈'完成即沉淀'是最被认可的差异化, 2 个愿意付费",
        "",
        CVStatus.READY,
        "ago_d11",
    ),
    # ===== 本月早期 ready (2 条, 演示 /report 本月范围 + 述职季度范围) =====
    (
        "Cockpit 自身",
        "启动 Cockpit v0.2 MVP",
        "从 skill 仓库 fork 出独立 web 产品",
        "启动 Cockpit v0.2 MVP, 从 task-cockpit skill 仓库 fork 出独立 web 产品, 5 周交付核心功能",
        "",
        CVStatus.READY,
        "ago_d18",
    ),
    (
        "Cockpit 自身",
        "FastAPI + Next.js 15 技术栈定稿",
        "对比 Flask / Django / Hono / Express, 选 FastAPI + Next.js",
        "定技术栈: FastAPI + SQLAlchemy 2.0 async + aiosqlite (后端) / Next.js 15 + SWR (前端), 兼顾开发效率和未来扩展",
        "",
        CVStatus.READY,
        "ago_d22",
    ),
    # ===== 很久以前 ready (1 条) — 已归档项目的成就 =====
    (
        "旧版 Landing Page 重构",
        "Landing Page 改版上线",
        "重构 1 周, 跳出率 -18%",
        "完成 Landing Page 改版上线, 跳出率 -18%, 转化率 +12%",
        "",
        CVStatus.READY,
        "ago_d75",  # 2.5 个月前, 演示归档项目
    ),
]


async def main(force: bool = False, dry_run: bool = False) -> None:
    print("=" * 60)
    print("Cockpit 演示数据播种")
    print("=" * 60)
    print()

    # === 警告 + 确认 ===
    if not force and not dry_run:
        print("⚠️  警告: 会清空当前 cockpit.db 里的项目/任务/成就/聊天 session")
        print("    LLM 设置 (settings 表) 保留")
        print()
        try:
            answer = input("继续? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            print("已取消")
            return
        if answer != "y":
            print("已取消")
            return
        print()

    if dry_run:
        print("[DRY-RUN] 不会写入数据库, 仅打印计划")
        print()

    # === 初始化 storage ===
    storage.init_engine()
    await storage.create_tables()

    # === 清空旧数据 (保留 settings) ===
    if not dry_run:
        async with storage.get_session() as session:
            from sqlalchemy import delete
            from app.core.storage import (
                AchievementORM,
                ChatMessageORM,
                ChatSessionORM,
                ProjectORM,
                TaskORM,
            )
            # 顺序: message → session → task → project → achievement
            await session.execute(delete(ChatMessageORM))
            await session.execute(delete(ChatSessionORM))
            await session.execute(delete(TaskORM))
            await session.execute(delete(ProjectORM))
            await session.execute(delete(AchievementORM))
        print("✓ 清空旧数据")
    print()

    # === 1. 创建项目 ===
    print(f"[1/3] 创建 {len(PROJECTS)} 个项目 (含 1 个已归档)")
    project_ids: dict[str, str] = {}
    for p in PROJECTS:
        if dry_run:
            print(f"  - {p['name']}{' [已归档]' if p['archived'] else ''}")
            project_ids[p["name"]] = f"proj_demo_{p['name']}"
            continue
        created = await storage.add_project(
            ProjectCreate(name=p["name"], description=p["description"])
        )
        if p["archived"]:
            from app.core.models import ProjectUpdate
            await storage.update_project(created.id, ProjectUpdate(archived=True))
        project_ids[p["name"]] = created.id
        flag = " [已归档]" if p["archived"] else ""
        print(f"  - {p['name']}{flag} → {created.id}")
    print()

    # === 2. 创建当前任务 (focus 5 来源) ===
    active_tasks = [t for t in TODAY_TASKS if not t.get("archived", False)]
    print(f"[2/3] 创建 {len(active_tasks)} 个当前任务 (focus 5 演示)")
    for t in active_tasks:
        if dry_run:
            print(f"  - [{t['priority'].value}] {t['title']}")
            continue
        pid = project_ids[t["project"]]
        created = await storage.add_task(
            TaskCreate(
                project=pid,
                title=t["title"],
                priority=t["priority"],
                due=t.get("due"),
                blocked=t.get("blocked", False),
            )
        )
        if t.get("status") == TaskStatus.IN_PROGRESS:
            from app.core.models import TaskUpdate
            await storage.update_task(created.id, TaskUpdate(status=TaskStatus.IN_PROGRESS))
    print()

    # === 3. 创建成就 (混合三态) ===
    print(f"[3/3] 创建 {len(ACHIEVEMENTS)} 条成就 (3 状态混合, 跨本周/上周/本月)")
    ready_count = sum(1 for a in ACHIEVEMENTS if a[5] == CVStatus.READY)
    needs_data_count = sum(1 for a in ACHIEVEMENTS if a[5] == CVStatus.NEEDS_DATA)
    pending_count = sum(1 for a in ACHIEVEMENTS if a[5] == CVStatus.PENDING)
    print(f"      ready: {ready_count} · needs_data: {needs_data_count} · pending: {pending_count}")
    print()
    for proj_name, title, outcome, cv, reflection, status, date_hint in ACHIEVEMENTS:
        target_date = _date_for_hint(date_hint)
        if dry_run:
            tag = {"ready": "✅", "needs_data": "📊", "pending": "⏳"}[status.value]
            days_diff = (TODAY - target_date).days
            # 正数 = N 天前, 0 = 今天, 负数 = 未来 (本周还没到的那天)
            when = (
                "今天" if days_diff == 0
                else f"{-days_diff}天后" if days_diff < 0
                else f"{days_diff}天前"
            )
            print(f"  {tag} [{when} / {target_date}] {proj_name} / {title}")
            continue
        pid = project_ids[proj_name]
        # 用 add_task + complete_task 模拟 (走 storage 完整流程, 触发 created_at 逻辑)
        task = await storage.add_task(
            TaskCreate(project=pid, title=f"__demo_{title[:30]}", priority=Priority.MEDIUM)
        )
        await storage.complete_task(
            task.id,
            outcome=outcome,
            cv=cv,
            reflection=reflection,
            cv_status=status,
        )
        # 把 created_at 改到对应日期 (complete 后 task 没了, achievement 的 date 是完成日期)
        # 这里用 storage 的 list_achievements 找到最新那条 update date 字段
        async with storage.get_session() as session:
            from sqlalchemy import select
            from app.core.storage import AchievementORM
            # 找刚 insert 的 (title 跟 title 匹配)
            stmt = select(AchievementORM).where(AchievementORM.title == f"__demo_{title[:30]}")
            result = await session.execute(stmt)
            ach = result.scalar_one_or_none()
            if ach:
                # 改 title 回去 (去掉 __demo_ 前缀)
                ach.title = title
                ach.date = target_date

    print()
    print("=" * 60)
    print("✓ 演示数据播种完成")
    print("=" * 60)
    print()
    print("可以这样看效果:")
    print()
    print("  /          → 看板, 看归档项目 (旧版 Landing Page 重构)")
    print("               + focus 5 (5 个任务, 含 1 个 blocked + 1 个今天 due)")
    print()
    print("  /today     → 晨间 ritual, 大日期 + focus 5 + 今天已完成")
    print("               (Q3 商业化的 1v1 跟邀请 dogfooding 都在 done_today)")
    print()
    print("  /report    → 周报/述职 workspace")
    print("               - 选 '本周' + '产品周报', 看草稿")
    print("               - 选 '本季度' + '述职材料', 只显示 ready 成就")
    print("               - 左侧 '📊 还差数据' 跟 '⏳ 草稿' 区各点几下升级")
    print("               - 切换编辑模式, 改两行, 点 '下载 .md'")
    print()
    print("  /achievements → 成就库")
    print("                 - 顶部过滤: 全部 / 📊 还差数据 / ⏳ 草稿 / ✅ ready")
    print("                 - 每条非 ready 右上角有 '升 ready' 按钮")


def cli() -> None:
    p = argparse.ArgumentParser(description="播种 Cockpit 演示数据")
    p.add_argument("--force", action="store_true", help="跳过确认提示")
    p.add_argument("--dry-run", action="store_true", help="只打印不写")
    args = p.parse_args()
    asyncio.run(main(force=args.force, dry_run=args.dry_run))


if __name__ == "__main__":
    cli()
