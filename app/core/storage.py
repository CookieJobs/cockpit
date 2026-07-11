"""Cockpit存储层（异步 SQLAlchemy 2.0 + aiosqlite）。

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
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.focus import sort_focus
from app.core.models import (
    Achievement,
    AchievementUpdate,
    ChatMessage,
    ChatSession,
    ChecklistItem,
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
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.NOT_STARTED.value)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default=Priority.MEDIUM.value)
    due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_action: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    draft: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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


class SettingsORM(Base):
    """全局设置表（key-value 形式）。

    用于存储运行时配置（LLM API key、用户偏好等）。
    key: 配置项名
    value: JSON 序列化值
    """
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChatSessionORM(Base):
    """对话 session 表。

    id 由前端生成（UUID），跨刷新保留；切换浏览器/隐身模式自动建新 session。

    注意：created_at/last_active_at 用 Python 端 datetime.now() 默认，
    不用 server_default=func.now()。原因：server default 在 flush 后
    要 refresh 才能读到新值，但 async SQLAlchemy 在 await 链外 lazy load
    会触发 MissingGreenlet。客户端 default 由 SQLAlchemy 直接写到对象上，
    无需 refresh。
    """
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(100), default="新对话", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ChatMessageORM(Base):
    """对话消息表。

    一条消息对应一轮 user/assistant 交互。content 存 Anthropic 格式的
    content list（JSON 字符串），LLM 客户端会自己转换。
    role: "user" | "assistant"
    """
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, index=True
    )


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
    """创建所有表 + 轻量级 schema migration。

    create_all 只创建缺失的表，不加新列。这里手动 ALTER TABLE 给已存在的表
    加 description 列（projects/tasks），保持向后兼容。
    """
    if _engine is None:
        init_engine()
    async with _engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)
        # Schema migrations（idempotent — 加过的列会报错被吞掉）
        await _migrate_add_column(conn, "projects", "description", "TEXT NOT NULL DEFAULT ''")
        await _migrate_add_column(conn, "tasks", "description", "TEXT NOT NULL DEFAULT ''")


async def _migrate_add_column(conn, table: str, column: str, col_type: str) -> None:
    """如果表存在但列不存在，加列。SQLite 无 IF NOT EXISTS 语法，用 try/except。"""
    try:
        await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        logger.info(f"Migrated: added {table}.{column}")
    except Exception:
        # 列已存在或其他原因 — 静默忽略
        pass


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
        description=p.description,
        created_at=p.created_at,
        archived=p.archived,
    )


def _task_to_pydantic(t: TaskORM) -> Task:
    raw = json.loads(t.checklist_json or "[]")
    # 兼容旧数据格式：list[str] → list[ChecklistItem]
    items: list[ChecklistItem] = []
    for x in raw:
        if isinstance(x, str):
            items.append(ChecklistItem(text=x, done=False))
        elif isinstance(x, dict):
            items.append(ChecklistItem(text=x.get("text", ""), done=x.get("done", False)))
    return Task(
        id=t.id,
        project=t.project_id,
        title=t.title,
        description=t.description,
        status=TaskStatus(t.status),
        priority=Priority(t.priority),
        due=t.due,
        next_action=t.next_action,
        blocked=t.blocked,
        draft=t.draft,
        created_at=t.created_at,
        completed_at=t.completed_at,
        checklist=items,
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


def _session_to_pydantic(s: ChatSessionORM, message_count: int = 0) -> ChatSession:
    return ChatSession(
        id=s.id,
        label=s.label,
        created_at=s.created_at,
        last_active_at=s.last_active_at,
        archived=s.archived,
        message_count=message_count,
    )


def _message_to_pydantic(m: ChatMessageORM) -> ChatMessage:
    return ChatMessage(
        id=m.id,
        session_id=m.session_id,
        role=m.role,
        content=m.content,
        tool_calls=json.loads(m.tool_calls_json) if m.tool_calls_json else None,
        created_at=m.created_at,
    )


# ===== CRUD: Projects =====


async def add_project(data: ProjectCreate) -> Project:
    async with get_session() as session:
        project = ProjectORM(
            id=_new_id("proj"),
            name=data.name,
            description=data.description,
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
        if data.description is not None:
            p.description = data.description
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
        # 序列化 checklist
        checklist_data = [item.model_dump() if hasattr(item, "model_dump") else item
                          for item in data.checklist]
        task = TaskORM(
            id=_new_id("task"),
            project_id=data.project,
            title=data.title,
            description=data.description,
            status=TaskStatus.NOT_STARTED.value,
            priority=data.priority.value,
            due=data.due,
            next_action=data.next_action,
            blocked=data.blocked,
            draft=False,  # 新建任务直接进入 todo，无需二次确认
            created_at=date.today(),
            checklist_json=json.dumps(checklist_data, ensure_ascii=False),
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
        if data.description is not None:
            t.description = data.description
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
            checklist_data = [item.model_dump() if hasattr(item, "model_dump") else item
                              for item in data.checklist]
            t.checklist_json = json.dumps(checklist_data, ensure_ascii=False)
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


# ===== Checklist =====


async def checklist_add(tid: str, text: str) -> Optional[Task]:
    """追加一个 checklist item 到任务。"""
    if not text.strip():
        return None
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        if not t:
            return None
        items = json.loads(t.checklist_json or "[]")
        items.append({"text": text.strip(), "done": False})
        t.checklist_json = json.dumps(items, ensure_ascii=False)
        await session.flush()
        return _task_to_pydantic(t)


async def checklist_toggle(tid: str, index: int) -> Optional[Task]:
    """切换 checklist item 的 done 状态。"""
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        if not t:
            return None
        items = json.loads(t.checklist_json or "[]")
        if index < 0 or index >= len(items):
            return None
        if isinstance(items[index], dict):
            items[index]["done"] = not items[index].get("done", False)
        else:
            # 旧格式：list[str]
            items[index] = {"text": str(items[index]), "done": True}
        t.checklist_json = json.dumps(items, ensure_ascii=False)
        await session.flush()
        return _task_to_pydantic(t)


async def checklist_remove(tid: str, index: int) -> Optional[Task]:
    """删除一个 checklist item。"""
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        if not t:
            return None
        items = json.loads(t.checklist_json or "[]")
        if index < 0 or index >= len(items):
            return None
        items.pop(index)
        t.checklist_json = json.dumps(items, ensure_ascii=False)
        await session.flush()
        return _task_to_pydantic(t)


# ===== Settings (key-value 存储) =====


async def get_setting(key: str) -> Optional[str]:
    """读取一个 setting（返回 JSON 字符串）。"""
    async with get_session() as session:
        result = await session.execute(select(SettingsORM).where(SettingsORM.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else None


async def set_setting(key: str, value: str) -> None:
    """设置一个 setting（upsert）。"""
    async with get_session() as session:
        result = await session.execute(select(SettingsORM).where(SettingsORM.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            session.add(SettingsORM(key=key, value=value))


async def delete_setting(key: str) -> bool:
    """删除一个 setting。"""
    async with get_session() as session:
        result = await session.execute(select(SettingsORM).where(SettingsORM.key == key))
        row = result.scalar_one_or_none()
        if not row:
            return False
        await session.delete(row)
        return True


# ===== CRUD: Chat Sessions =====


async def create_chat_session(session_id: str, label: str = "新对话") -> ChatSession:
    """创建新 session（id 由前端提供）。"""
    async with get_session() as session:
        s = ChatSessionORM(id=session_id, label=label)
        session.add(s)
        await session.flush()
        return _session_to_pydantic(s, message_count=0)


async def get_chat_session(session_id: str) -> Optional[ChatSession]:
    """取单个 session（含 message_count）。"""
    async with get_session() as session:
        result = await session.execute(
            select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return None
        count_result = await session.execute(
            select(func.count(ChatMessageORM.id)).where(ChatMessageORM.session_id == session_id)
        )
        msg_count = count_result.scalar_one()
        return _session_to_pydantic(s, message_count=int(msg_count or 0))


async def list_chat_sessions(include_archived: bool = False, limit: int = 50) -> list[ChatSession]:
    """列出活跃 session（按 last_active_at desc）。"""
    async with get_session() as session:
        stmt = select(ChatSessionORM).order_by(ChatSessionORM.last_active_at.desc()).limit(limit)
        if not include_archived:
            stmt = stmt.where(ChatSessionORM.archived.is_(False))
        result = await session.execute(stmt)
        sessions = result.scalars().all()
        # 批量算 message_count
        out: list[ChatSession] = []
        for s in sessions:
            count_result = await session.execute(
                select(func.count(ChatMessageORM.id)).where(ChatMessageORM.session_id == s.id)
            )
            msg_count = count_result.scalar_one()
            out.append(_session_to_pydantic(s, message_count=int(msg_count or 0)))
        return out


async def touch_chat_session(session_id: str) -> None:
    """更新 last_active_at（每次新消息后调用）。"""
    async with get_session() as session:
        result = await session.execute(
            select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return
        s.last_active_at = datetime.now()


async def rename_chat_session(session_id: str, label: str) -> Optional[ChatSession]:
    """重命名 session。"""
    async with get_session() as session:
        result = await session.execute(
            select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return None
        s.label = label[:100]
        await session.flush()
        count_result = await session.execute(
            select(func.count(ChatMessageORM.id)).where(ChatMessageORM.session_id == session_id)
        )
        msg_count = count_result.scalar_one()
        return _session_to_pydantic(s, message_count=int(msg_count or 0))


async def archive_chat_session(session_id: str, archived: bool = True) -> Optional[ChatSession]:
    """归档/取消归档 session。"""
    async with get_session() as session:
        result = await session.execute(
            select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return None
        s.archived = archived
        await session.flush()
        count_result = await session.execute(
            select(func.count(ChatMessageORM.id)).where(ChatMessageORM.session_id == session_id)
        )
        msg_count = count_result.scalar_one()
        return _session_to_pydantic(s, message_count=int(msg_count or 0))


async def delete_chat_session(session_id: str) -> bool:
    """删除 session（级联删 messages）。

    注意：SQLite 默认不强制外键，DB 级 ON DELETE CASCADE 不生效。
    这里手动先删 messages（参考 delete_project 对 tasks 的处理）。
    """
    async with get_session() as session:
        # 先删 messages
        await session.execute(
            delete(ChatMessageORM).where(ChatMessageORM.session_id == session_id)
        )
        # 再删 session
        result = await session.execute(
            select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return False
        await session.delete(s)
        return True


# ===== CRUD: Chat Messages =====


async def add_chat_message(
    session_id: str,
    role: str,
    content: str,
    tool_calls: Optional[list[dict]] = None,
) -> ChatMessage:
    """追加一条消息到 session。"""
    async with get_session() as session:
        m = ChatMessageORM(
            id=_new_id("msg"),
            session_id=session_id,
            role=role,
            content=content,
            tool_calls_json=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
        )
        session.add(m)
        await session.flush()
        # 顺手更新 session 的 last_active_at
        result = await session.execute(
            select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        )
        s = result.scalar_one_or_none()
        if s:
            s.last_active_at = datetime.now()
        return _message_to_pydantic(m)


async def list_chat_messages(session_id: str, limit: int = 40) -> list[ChatMessage]:
    """取 session 最近 N 条消息（按时间正序）。"""
    async with get_session() as session:
        result = await session.execute(
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at.desc())
            .limit(limit)
        )
        # 反转成正序（从旧到新）
        msgs = list(reversed(result.scalars().all()))
        return [_message_to_pydantic(m) for m in msgs]


async def append_chat_turn(
    session_id: str,
    user_content: str,
    assistant_content: str,
    assistant_tool_calls: Optional[list[dict]] = None,
) -> tuple[ChatMessage, ChatMessage]:
    """追加完整一轮（user + assistant），返回两条消息。"""
    user_msg = await add_chat_message(session_id, "user", user_content)
    assistant_msg = await add_chat_message(
        session_id, "assistant", assistant_content, tool_calls=assistant_tool_calls
    )
    return user_msg, assistant_msg


async def load_chat_history_for_llm(
    session_id: str, limit: int = 40
) -> list[dict]:
    """加载 session 历史给 LLM（返回 Anthropic 格式的消息列表）。

    返回的消息格式：
    - {"role": "user", "content": "..."} 或
    - {"role": "assistant", "content": [{"type": "text", "text": "..."}, {"type": "tool_use", ...}]}
    """
    msgs = await list_chat_messages(session_id, limit=limit)
    result: list[dict] = []
    for m in msgs:
        try:
            # content 是 JSON 字符串（Anthropic content list）
            parsed = json.loads(m.content)
            if isinstance(parsed, list):
                result.append({"role": m.role, "content": parsed})
            else:
                # 兜底：纯文本
                result.append({"role": m.role, "content": str(parsed)})
        except (json.JSONDecodeError, TypeError):
            # 兜底：纯文本
            result.append({"role": m.role, "content": m.content})
    return result


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
