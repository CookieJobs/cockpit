"""拾光存储层（异步 SQLAlchemy 2.0 + aiosqlite）。

设计原则：
- 异步 SQLAlchemy 2.0 + aiosqlite（本地默认）
- 原子写入：complete_task / undo 使用"先写后删/先恢复后删"模式，中途崩溃不丢数据
- 字符串 ID（与 skill 兼容，便于数据迁移）
- Achievement append-only（除 cv/cvStatus 外不更新）
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.focus import sort_focus
from app.core.models import (
    Achievement,
    AchievementUpdate,
    CVStatus,
    FocusItem,
    Priority,
    Project,
    ProjectCreate,
    ProjectSnapshot,
    ProjectUpdate,
    Snapshot,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    _new_id,
)
from app.core.config import settings


# ===== ORM =====


class Base(DeclarativeBase):
    pass


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.NOT_STARTED.value)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default=Priority.MEDIUM.value)
    due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_action: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    draft: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    completed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    checklist_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


class AchievementORM(Base):
    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project: Mapped[str] = mapped_column(String(200), nullable=False)  # 名称快照
    title: Mapped[str] = mapped_column(String(500), nullable=False)  # 标题快照
    outcome: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reflection: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cv: Mapped[str] = mapped_column(Text, default="", nullable=False)
    cv_status: Mapped[str] = mapped_column(String(20), nullable=False, default=CVStatus.READY.value)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)


# ===== Engine & Session =====


_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def init_engine(database_url: Optional[str] = None) -> None:
    """初始化数据库引擎。"""
    global _engine, _session_factory
    url = database_url or settings.get_database_url()
    _engine = create_async_engine(url, echo=False, future=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def reset_engine() -> None:
    """重置引擎（测试用）。"""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def create_tables() -> None:
    """创建所有表。"""
    if _engine is None:
        init_engine()
    async with _engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """删除所有表（测试用）。"""
    if _engine is None:
        init_engine()
    async with _engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.drop_all)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """获取数据库会话（自动 commit/rollback）。"""
    if _session_factory is None:
        init_engine()
    async with _session_factory() as session:  # type: ignore[union-attr]
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ===== Converters =====


def _project_to_pydantic(p: ProjectORM) -> Project:
    return Project(
        id=p.id,
        name=p.name,
        created_at=p.created_at,
        archived=p.archived,
    )


def _task_to_pydantic(t: TaskORM) -> Task:
    return Task(
        id=t.id,
        project=t.project_id,
        title=t.title,
        status=TaskStatus(t.status),
        priority=Priority(t.priority),
        due=t.due,
        next_action=t.next_action,
        blocked=t.blocked,
        draft=t.draft,
        created_at=t.created_at,
        completed_at=t.completed_at,
        checklist=json.loads(t.checklist_json or "[]"),
    )


def _achievement_to_pydantic(a: AchievementORM) -> Achievement:
    return Achievement(
        id=a.id,
        date=a.date,
        task_id=a.task_id,
        project_id=a.project_id,
        project=a.project,
        title=a.title,
        outcome=a.outcome,
        reflection=a.reflection,
        cv=a.cv,
        cv_status=CVStatus(a.cv_status),
        tags=json.loads(a.tags_json or "[]"),
    )


# ===== CRUD: Projects =====


async def add_project(data: ProjectCreate) -> Project:
    async with get_session() as session:
        project = ProjectORM(
            id=_new_id("proj"),
            name=data.name,
            created_at=date.today(),
            archived=False,
        )
        session.add(project)
        await session.flush()
        return _project_to_pydantic(project)


async def get_project(pid: str) -> Optional[Project]:
    async with get_session() as session:
        result = await session.execute(select(ProjectORM).where(ProjectORM.id == pid))
        p = result.scalar_one_or_none()
        return _project_to_pydantic(p) if p else None


async def list_projects(include_archived: bool = False) -> list[Project]:
    async with get_session() as session:
        stmt = select(ProjectORM).order_by(ProjectORM.created_at)
        if not include_archived:
            stmt = stmt.where(ProjectORM.archived.is_(False))
        result = await session.execute(stmt)
        return [_project_to_pydantic(p) for p in result.scalars()]


async def update_project(pid: str, data: ProjectUpdate) -> Optional[Project]:
    async with get_session() as session:
        result = await session.execute(select(ProjectORM).where(ProjectORM.id == pid))
        p = result.scalar_one_or_none()
        if not p:
            return None
        if data.name is not None:
            p.name = data.name
        if data.archived is not None:
            p.archived = data.archived
        await session.flush()
        return _project_to_pydantic(p)


async def delete_project(pid: str) -> bool:
    async with get_session() as session:
        result = await session.execute(select(ProjectORM).where(ProjectORM.id == pid))
        p = result.scalar_one_or_none()
        if not p:
            return False
        # 级联删除任务
        await session.execute(delete(TaskORM).where(TaskORM.project_id == pid))
        await session.delete(p)
        return True


# ===== CRUD: Tasks =====


async def add_task(data: TaskCreate) -> Task:
    async with get_session() as session:
        # 验证项目存在
        result = await session.execute(select(ProjectORM).where(ProjectORM.id == data.project))
        if not result.scalar_one_or_none():
            raise ValueError(f"Project {data.project} not found")
        task = TaskORM(
            id=_new_id("task"),
            project_id=data.project,
            title=data.title,
            status=TaskStatus.NOT_STARTED.value,
            priority=data.priority.value,
            due=data.due,
            next_action=data.next_action,
            blocked=data.blocked,
            draft=True,
            created_at=date.today(),
            checklist_json=json.dumps(data.checklist, ensure_ascii=False),
        )
        session.add(task)
        await session.flush()
        return _task_to_pydantic(task)


async def get_task(tid: str) -> Optional[Task]:
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        return _task_to_pydantic(t) if t else None


async def list_tasks(project_id: Optional[str] = None) -> list[Task]:
    async with get_session() as session:
        stmt = select(TaskORM).order_by(TaskORM.created_at)
        if project_id:
            stmt = stmt.where(TaskORM.project_id == project_id)
        result = await session.execute(stmt)
        return [_task_to_pydantic(t) for t in result.scalars()]


async def update_task(tid: str, data: TaskUpdate) -> Optional[Task]:
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        if not t:
            return None
        if data.title is not None:
            t.title = data.title
        if data.priority is not None:
            t.priority = data.priority.value
        if data.status is not None:
            t.status = data.status.value
        if data.due is not None:
            t.due = data.due
        if data.next_action is not None:
            t.next_action = data.next_action
        if data.blocked is not None:
            t.blocked = data.blocked
        if data.draft is not None:
            t.draft = data.draft
        if data.checklist is not None:
            t.checklist_json = json.dumps(data.checklist, ensure_ascii=False)
        await session.flush()
        return _task_to_pydantic(t)


async def confirm_all_drafts() -> int:
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.draft.is_(True)))
        count = 0
        for t in result.scalars():
            t.draft = False
            count += 1
        return count


async def delete_task(tid: str) -> bool:
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        if not t:
            return False
        await session.delete(t)
        return True


# ===== CRUD: Achievements =====


async def complete_task(
    task_id: str,
    outcome: str = "",
    reflection: str = "",
    cv: str = "",
    cv_status: CVStatus = CVStatus.READY,
) -> Optional[Achievement]:
    """完成任务并沉淀为成就。

    继承自 skill 的设计：先写 achievement，再删 task。中途崩溃会留 duplicate 但不丢数据。
    """
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return None
        # 拿项目名称做快照
        proj_result = await session.execute(
            select(ProjectORM).where(ProjectORM.id == task.project_id)
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {task.project_id} not found")
        # 先写 achievement（崩溃恢复点：这里写了 task 还没删，可以人工恢复）
        achievement = AchievementORM(
            id=_new_id("done"),
            date=date.today(),
            task_id=task.id,
            project_id=task.project_id,
            project=project.name,
            title=task.title,
            outcome=outcome,
            reflection=reflection,
            cv=cv,
            cv_status=cv_status.value,
            tags_json="[]",
        )
        session.add(achievement)
        await session.flush()
        # 再删 task
        await session.delete(task)
        return _achievement_to_pydantic(achievement)


async def update_achievement_cv(aid: str, data: AchievementUpdate) -> Optional[Achievement]:
    async with get_session() as session:
        result = await session.execute(select(AchievementORM).where(AchievementORM.id == aid))
        a = result.scalar_one_or_none()
        if not a:
            return None
        if data.cv is not None:
            a.cv = data.cv
        if data.cv_status is not None:
            a.cv_status = data.cv_status.value
        await session.flush()
        return _achievement_to_pydantic(a)


async def list_achievements(
    project_name: Optional[str] = None,
    since: Optional[date] = None,
    only_ready: bool = False,
) -> list[Achievement]:
    async with get_session() as session:
        stmt = select(AchievementORM).order_by(AchievementORM.date.desc())
        if project_name:
            stmt = stmt.where(AchievementORM.project == project_name)
        if since:
            stmt = stmt.where(AchievementORM.date >= since)
        if only_ready:
            stmt = stmt.where(AchievementORM.cv_status == CVStatus.READY.value)
        result = await session.execute(stmt)
        return [_achievement_to_pydantic(a) for a in result.scalars()]


async def undo_completion(aid: str) -> Optional[Task]:
    """撤销完成：恢复 task，删除 achievement。

    镜像 complete_task：先恢复 task，再删 achievement。中途崩溃会留 duplicate 但可恢复。
    """
    async with get_session() as session:
        result = await session.execute(select(AchievementORM).where(AchievementORM.id == aid))
        achievement = result.scalar_one_or_none()
        if not achievement:
            return None
        # 拿项目验证
        proj_result = await session.execute(
            select(ProjectORM).where(ProjectORM.id == achievement.project_id)
        )
        if not proj_result.scalar_one_or_none():
            raise ValueError(f"Project {achievement.project_id} not found")
        # 先恢复 task
        task = TaskORM(
            id=achievement.task_id,
            project_id=achievement.project_id,
            title=achievement.title,
            status=TaskStatus.IN_PROGRESS.value,
            priority=Priority.MEDIUM.value,
            due=None,
            next_action="",
            blocked=False,
            draft=False,
            created_at=date.today(),
            completed_at=None,
            checklist_json="[]",
        )
        session.add(task)
        await session.flush()
        # 再删 achievement
        await session.delete(achievement)
        return _task_to_pydantic(task)


# ===== Snapshot =====


async def build_snapshot() -> Snapshot:
    """构建全局快照（dashboard / 问局势 用）。"""
    async with get_session() as session:
        proj_result = await session.execute(select(ProjectORM))
        all_projects = proj_result.scalars().all()

        task_result = await session.execute(select(TaskORM))
        all_tasks = [_task_to_pydantic(t) for t in task_result.scalars().all()]

        today = date.today()
        ach_result = await session.execute(
            select(AchievementORM).where(AchievementORM.date == today)
        )
        done_today = [_achievement_to_pydantic(a) for a in ach_result.scalars().all()]

        all_ach_result = await session.execute(select(AchievementORM))
        all_achievements = all_ach_result.scalars().all()
        ready_count = sum(1 for a in all_achievements if a.cv_status == CVStatus.READY.value)
        pending_count = sum(1 for a in all_achievements if a.cv_status == CVStatus.PENDING.value)

    # 算 focus
    focus_tasks = sort_focus(all_tasks)[:5]
    focus = [
        FocusItem(
            id=t.id,
            project=t.project,
            title=t.title,
            priority=t.priority,
            due=t.due,
            blocked=t.blocked,
            next_action=t.next_action,
        )
        for t in focus_tasks
    ]

    # 按 project 分组
    known_pids = {p.id for p in all_projects}
    projects_grouped: list[ProjectSnapshot] = []
    for p in all_projects:
        if p.archived:
            continue
        p_tasks = [t for t in all_tasks if t.project == p.id]
        projects_grouped.append(ProjectSnapshot(
            id=p.id, name=p.name, tasks=p_tasks
        ))

    # 未分组的 task
    orphans = [t for t in all_tasks if t.project not in known_pids]
    if orphans:
        projects_grouped.append(ProjectSnapshot(id=None, name="未分组", tasks=orphans))

    return Snapshot(
        focus=focus,
        projects=projects_grouped,
        done_today=done_today,
        counts={
            "achievementsReady": ready_count,
            "achievementsPending": pending_count,
        },
    )
