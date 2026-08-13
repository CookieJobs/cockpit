"""Cockpit存储层（异步 SQLAlchemy 2.0 + aiosqlite）。

设计原则：
- 异步 SQLAlchemy 2.0 + aiosqlite（本地默认）
- 原子写入：complete_task / undo 使用"先写后删/先恢复后删"模式，中途崩溃不丢数据
- 字符串 ID（与 skill 兼容，便于数据迁移）
- Achievement append-only（除 cv/cvStatus 外不更新）
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, delete, event, func, select
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
from app.core.config import DataRecoveryRequired, settings
from app.harness.l1 import evaluate_l1
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)


# ===== ORM =====


class Base(DeclarativeBase):
    pass


# ===== Reusable ORM mixins (2026-07-22 抽) =====
#
# 背景：6 个 ORM 类原本每张表都重写 `id: Mapped[str] = mapped_column(String(64), primary_key=True)`
# 和时间戳 boilerplate (created_at/last_active_at/updated_at)。抽出 4 个 mixin:
#   - StringPKMixin: 字符串主键 (String(64), 应用层生成 UUID/ulid)
#   - CreatedDateMixin: created_at: date, default=date.today
#   - CreatedDateTimeMixin: created_at: datetime, default=datetime.now
#   - LastActiveDateTimeMixin: last_active_at: datetime, default + onupdate
#   - UpdatedDateTimeMixin: updated_at: datetime, server_default=func.now() + onupdate
#
# 收益：
#   - 未来加新表零 boilerplate
#   - 字段类型统一 (String(64) 不再各处手抄, default 类型不再有人忘加)
#   - 防止 lesson #10 (build_snapshot 漏传 description) 类型的 silent failure
#
# 不参与 mixin 的 ORM (保留手写字段)：
#   - SettingsORM: 主键是 `key` 不是 `id`, 语义是 key-value 不是 entity
#   - AchievementORM: 字段名是 `date` 不是 `created_at`, 语义是"完成日" 不是"创建日"
#     (Achievement 一旦写入就不变, date 是业务日期不是系统时间戳)
# 它们的 boilerplate 跟其他 ORM 不同源, 抽 mixin 反而损失语义清晰度。


class StringPKMixin:
    """字符串主键 (应用层生成 UUID/ulid)。"""
    id: Mapped[str] = mapped_column(String(64), primary_key=True)


class CreatedDateMixin:
    """创建时间 (按日历日, 用于 Project/Task 这种"哪天立项"语义)。"""
    created_at: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)


class CreatedDateTimeMixin:
    """创建时间 (按时间戳, 用于 ChatSession/ChatMessage 这种"何时发生"语义)。

    用 Python 端 datetime.now() 默认, 不用 server_default=func.now()。
    原因: server default 在 flush 后要 refresh 才能读到新值, 但 async SQLAlchemy
    在 await 链外 lazy load 会触发 MissingGreenlet (lesson #8 教训)。
    客户端 default 由 SQLAlchemy 直接写到对象上, 无需 refresh。
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )


class LastActiveDateTimeMixin:
    """最后活跃时间 (Python 端 default + onupdate, 客户端维护, 同上避免 MissingGreenlet)。"""
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class UpdatedDateTimeMixin:
    """更新时间 (服务端 default + onupdate, 用于 Settings 这种少写多读的配置表)。

    用 server_default=func.now() + onupdate=func.now(), 由 SQLite 维护,
    应用层不读写。适合几乎只通过 ORM 写一次的配置表, 避免 async refresh。
    """
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProjectORM(StringPKMixin, CreatedDateMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 2026-07-30: 拖动排序。间隔 10 存 (0/10/20/...), 跟 Task 同样策略。
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    # 2026-08-11: 用户手动指定的项目 emoji (NULL = 用 hash 兜底, 保持老数据视觉稳定)。
    emoji: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class TaskORM(StringPKMixin, CreatedDateMixin, Base):
    __tablename__ = "tasks"

    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.NOT_STARTED.value)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default=Priority.P2.value)
    due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    checklist_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # 2026-07-30: 项目内拖动排序。
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)


class AchievementORM(Base):
    """成就表 (append-only, 完成一条 task 就写一行, task 删 task 改 achievement 留底)。

    字段 `date` 保留手写, 不进 CreatedDateMixin:
      语义是"哪天完成的" 业务日期, 不是"行何时创建" 系统时间戳
      (批量补录/数据迁移时 date 可能跟 created_at 差几天)
    """
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
    # 2026-08-01: LLM 主动追问 (JSON 数组, 旧数据默认 [])
    follow_up_questions_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # 2026-08-01: 用户对追问的答案 (JSON dict {q_idx: answer})
    follow_up_answers_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    distillation_trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)


class SettingsORM(UpdatedDateTimeMixin, Base):
    """全局设置表（key-value 形式）。

    用于存储运行时配置（LLM API key、用户偏好等）。
    key: 配置项名 (主键, 不用 StringPKMixin 因为字段名是 key 不是 id, 语义不同)
    value: JSON 序列化值
    """
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class ChatSessionORM(StringPKMixin, CreatedDateTimeMixin, LastActiveDateTimeMixin, Base):
    """对话 session 表。

    id 由前端生成（UUID），跨刷新保留；切换浏览器/隐身模式自动建新 session。
    """
    __tablename__ = "chat_sessions"

    label: Mapped[str] = mapped_column(String(100), default="新对话", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ChatMessageORM(StringPKMixin, CreatedDateTimeMixin, Base):
    """对话消息表。

    一条消息对应一轮 user/assistant 交互。content 存 Anthropic 格式的
    content list（JSON 字符串），LLM 客户端会自己转换。
    role: "user" | "assistant"
    """
    __tablename__ = "chat_messages"

    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DistillationTraceORM(StringPKMixin, CreatedDateTimeMixin, Base):
    """Append-only audit trace for a single achievement-distillation call."""
    __tablename__ = "distillation_traces"

    task_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    task_title: Mapped[str] = mapped_column(String(500), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    parsed_output_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    generator_status: Mapped[str] = mapped_column(String(20), nullable=False)
    guardrail_results_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    final_quality_status: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    harness_version: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int] = mapped_column(nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DistillationFeedbackORM(StringPKMixin, CreatedDateTimeMixin, Base):
    """Append-only record of a human edit to a generated CV statement."""
    __tablename__ = "distillation_feedback"

    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_cv: Mapped[str] = mapped_column(Text, nullable=False)
    final_cv: Mapped[str] = mapped_column(Text, nullable=False)
    edit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    diff_json: Mapped[str] = mapped_column(Text, nullable=False)


# ===== Engine & Session =====


_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _recovery_write_block_message() -> str | None:
    state = settings.data_recovery_state()
    if state and state.kind in {"conflict", "failed"}:
        return state.message or "数据恢复尚未完成；写入已暂停。"
    return None


@event.listens_for(AsyncSession.sync_session_class, "before_flush")
def _block_writes_during_data_recovery(_session, _flush_context, _instances) -> None:
    """Preserve read-only diagnostics while a DB migration conflict is unresolved."""
    if message := _recovery_write_block_message():
        raise DataRecoveryRequired(message)


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
    if message := _recovery_write_block_message():
        logger.warning("Skipping schema writes while data recovery is required: %s", message)
        return
    if _engine is None:
        init_engine()
    async with _engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)
        await _run_schema_migrations(conn)


async def run_schema_migrations() -> Path | None:
    """Run idempotent schema migrations and return a backup made for draft retirement.

    Kept public for an isolated migration test; normal application startup calls the
    same implementation from :func:`create_tables` after creating missing tables.
    """
    if _engine is None:
        init_engine()
    async with _engine.begin() as conn:  # type: ignore[union-attr]
        return await _run_schema_migrations(conn)


async def _run_schema_migrations(conn) -> Path | None:
    """Apply additive migrations, then the backup-first draft-column retirement."""
    # Schema migrations（idempotent — 加过的列会报错被吞掉）
    await _migrate_add_column(conn, "projects", "description", "TEXT NOT NULL DEFAULT ''")
    await _migrate_add_column(conn, "tasks", "description", "TEXT NOT NULL DEFAULT ''")
    # 2026-07-17: 删 next_action 列（与 description 语义重复，UI 早已不用）
    await _migrate_drop_column(conn, "tasks", "next_action")
    # 2026-07-22: priority 旧值 (高/中/低) → 新值 (P0/P2/P3) 一次性迁移
    await _migrate_priority_values(conn)
    # 2026-07-30: 拖动排序字段。老数据 sort_order 全 0, list 排序用 secondary
    # created_at ASC fallback, 创建顺序自然保留。
    await _migrate_add_column(conn, "projects", "sort_order", "INTEGER NOT NULL DEFAULT 0")
    await _migrate_add_column(conn, "tasks", "sort_order", "INTEGER NOT NULL DEFAULT 0")
    # 2026-08-01: follow_up_questions / answers 字段 (LLM 主动追问 + 用户答案)
    await _migrate_add_column(conn, "achievements", "follow_up_questions_json", "TEXT NOT NULL DEFAULT '[]'")
    await _migrate_add_column(conn, "achievements", "follow_up_answers_json", "TEXT NOT NULL DEFAULT '{}'")
    await _migrate_add_column(conn, "achievements", "distillation_trace_id", "TEXT")
    # 2026-08-01: task.completed_at 字段 (task 保留后记录何时完成)
    await _migrate_add_column(conn, "tasks", "completed_at", "DATE")
    # 2026-08-11: project.emoji 字段 (NULL 允许, 老数据走 hash 兜底零破坏)
    await _migrate_add_column(conn, "projects", "emoji", "VARCHAR(32)")
    return await _migrate_drop_task_draft_column(conn)


async def _migrate_drop_task_draft_column(conn) -> Path | None:
    """Back up and retire ``tasks.draft`` while preserving every historical task.

    A legacy draft only meant "not yet confirmed". Once the product state is
    removed, the row remains an ordinary unfinished task with all other values
    untouched. The column check makes startup repeats a strict no-op.
    """
    try:
        column_rows = (await conn.exec_driver_sql("PRAGMA table_info(tasks)")).fetchall()
    except Exception:
        return None
    if "draft" not in {row[1] for row in column_rows}:
        return None

    database_rows = (await conn.exec_driver_sql("PRAGMA database_list")).fetchall()
    database_path = next((Path(row[2]) for row in database_rows if row[1] == "main" and row[2]), None)
    if database_path is None:
        raise RuntimeError("Cannot back up the task draft migration database before changing its schema")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = database_path.with_name(
        f"{database_path.stem}.before-task-draft-retirement-{timestamp}-{uuid.uuid4().hex[:8]}{database_path.suffix}"
    )
    shutil.copy2(database_path, backup_path)
    await conn.exec_driver_sql("ALTER TABLE tasks DROP COLUMN draft")
    logger.info("Retired tasks.draft after backup: %s", backup_path)
    return backup_path


async def _migrate_priority_values(conn) -> None:
    """把旧 priority 值 (高/中/低) 一次性映射到新值 (P0/P2/P3)。

    2026-07-22 立: Priority enum 从 3 档 (高/中/低) 升级到 4 档 (P0/P1/P2/P3)。
    旧 DB 里的 "高/中/低" 不在新 enum 里, 加载会报 ValidationError。
    启动时跑一次 UPDATE 兼容老数据。

    映射规则 (4 档换 3 档, 选最接近的):
    - 高 → P0 (紧急 / 最高优先级, P0 在 4 档里对应"最急"那档)
    - 中 → P2 (普通, 4 档的默认档)
    - 低 → P3 (不急)
    - P1 (高但非紧急) 是新档, 旧数据无对应 — 用户后续手动调整

    幂等: WHERE 限定只更新老值, 已经迁移过的 P0/P1/P2/P3 行不再 touch。
    """
    try:
        result = await conn.exec_driver_sql(
            "UPDATE tasks SET priority = CASE priority "
            "WHEN '高' THEN 'P0' "
            "WHEN '中' THEN 'P2' "
            "WHEN '低' THEN 'P3' "
            "ELSE priority END "
            "WHERE priority IN ('高', '中', '低')"
        )
        # SQLite 3.x driver returns cursor with rowcount; log if anything was changed.
        rowcount = result.rowcount if hasattr(result, "rowcount") else 0
        if rowcount:
            logger.info(f"Migrated priority values: {rowcount} task(s) updated (高→P0/中→P2/低→P3)")
    except Exception as e:
        # 任何错都吞掉 — 启动不该因 migration 失败而死, 留给 pydantic ValidationError
        # 在 add_task/update_task 那一层报错更友好
        logger.warning(f"Priority migration skipped: {e}")


async def _migrate_add_column(conn, table: str, column: str, col_type: str) -> None:
    """如果表存在但列不存在，加列。SQLite 无 IF NOT EXISTS 语法，用 try/except。"""
    try:
        await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        logger.info(f"Migrated: added {table}.{column}")
    except Exception:
        # 列已存在或其他原因 — 静默忽略
        pass


async def _migrate_drop_column(conn, table: str, column: str) -> None:
    """如果表存在且列存在，删列。SQLite 3.35+ 支持 ALTER TABLE DROP COLUMN。

    旧版本 / 列不存在会抛错被吞掉 — 安全幂等。注意 SQLite DROP COLUMN 有
    限制（列不能被索引、不能是 PK、不能有 CHECK 约束引用等），违反会失败，
    也走静默 ignore（用户已决定硬删 — 失败说明 schema 卡住，需要人工处理）。
    """
    try:
        await conn.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN {column}")
    except Exception:
        # 列已不存在或 DROP 失败 — 静默忽略
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
        sort_order=p.sort_order,
        emoji=p.emoji,
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
        blocked=t.blocked,
        created_at=t.created_at,
        completed_at=t.completed_at,
        checklist=items,
        sort_order=t.sort_order,
    )


def _achievement_to_pydantic(a: AchievementORM, *, unmet_reasons: Optional[list[str]] = None) -> Achievement:
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
        # 2026-08-01: 解析 follow_up_questions / answers, 旧数据默认 []/{}
        follow_up_questions=json.loads(a.follow_up_questions_json or "[]"),
        follow_up_answers=json.loads(a.follow_up_answers_json or "{}"),
        distillation_trace_id=a.distillation_trace_id,
        unmet_reasons=unmet_reasons or [],
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
        # 2026-07-30: 新加项目 sort_order = max + 10, 排在最后
        new_order = await _next_sort_order(session, ProjectORM)
        project = ProjectORM(
            id=_new_id("proj"),
            name=data.name,
            description=data.description,
            created_at=date.today(),
            archived=False,
            sort_order=new_order,
            emoji=data.emoji,
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
        # 2026-07-30: 拖动排序。sort_order ASC 主排序, created_at ASC 二级 fallback
        #   (老数据 sort_order 全 0, 跟创建顺序一致; 用户拖过后 sort_order 拉开差异)
        stmt = select(ProjectORM).order_by(ProjectORM.sort_order.asc(), ProjectORM.created_at.asc())
        if not include_archived:
            stmt = stmt.where(ProjectORM.archived.is_(False))
        result = await session.execute(stmt)
        return [_project_to_pydantic(p) for p in result.scalars()]


async def _next_sort_order(session: AsyncSession, model) -> int:
    """给新加 row 计算 sort_order = max(existing) + 10。

    2026-07-30 立: 拖动排序配套。新加的 task/project 排在最后, 用户拖动产生
    的 sort_order 间隔 (10) 不会被破坏。
    - 表为空 (max=None) → 0 (第一个 row 从 0 开始, 跟 list 排序对齐)
    - 表非空 → max + 10 (永远在最后)
    """
    result = await session.execute(select(func.max(model.sort_order)))
    current_max = result.scalar()
    if current_max is None:
        return 0
    return current_max + 10


async def _next_sort_order_for_project(session: AsyncSession, project_id: str) -> int:
    """项目内新加 task 计算 sort_order = max(project 内) + 10。

    任务排序是项目内独立的, 不能跨项目取 max。空项目返回 0 (跟默认对齐)。
    """
    result = await session.execute(
        select(func.max(TaskORM.sort_order)).where(TaskORM.project_id == project_id)
    )
    current_max = result.scalar()
    if current_max is None:
        return 0
    return current_max + 10


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
        # emoji 字段: None = 不传 (不改), "" = 显式清空, 其他 = 设置。
        # Pydantic Optional 字段缺省 None, 显式传 "" 也会触发这个分支 (is not None)。
        if data.emoji is not None:
            p.emoji = data.emoji if data.emoji else None
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


async def project_deletion_preview(pid: str) -> dict[str, int | str] | None:
    """Return the full local impact before the advanced deletion boundary."""
    async with get_session() as session:
        project = (await session.execute(select(ProjectORM).where(ProjectORM.id == pid))).scalar_one_or_none()
        if not project:
            return None
        task_count = (await session.execute(
            select(func.count()).select_from(TaskORM).where(TaskORM.project_id == pid)
        )).scalar_one()
        achievement_count = (await session.execute(
            select(func.count()).select_from(AchievementORM).where(AchievementORM.project_id == pid)
        )).scalar_one()
        return {
            "project_id": project.id,
            "project_name": project.name,
            "task_count": task_count,
            "achievement_count": achievement_count,
        }


async def create_database_backup(reason: str) -> Path:
    """Create a local, timestamped backup before a dangerous operation."""
    if _engine is None:
        init_engine()
    async with _engine.connect() as conn:  # type: ignore[union-attr]
        database_rows = (await conn.exec_driver_sql("PRAGMA database_list")).fetchall()
    database_path = next((Path(row[2]) for row in database_rows if row[1] == "main" and row[2]), None)
    if database_path is None:
        raise RuntimeError("Cannot create a recoverable backup for an in-memory database")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = database_path.with_name(
        f"{database_path.stem}.before-{reason}-{timestamp}-{uuid.uuid4().hex[:8]}{database_path.suffix}"
    )
    shutil.copy2(database_path, backup_path)
    return backup_path


async def advanced_delete_project(pid: str, project_name: str) -> dict[str, object] | None:
    """Backup, confirm by exact name, and protect achievement-bearing projects.

    The asset policy is intentionally conservative: a project with achievements
    is never permanently deleted. The caller receives an actionable conflict and
    should offer archive (the default project-management action) instead.
    """
    preview = await project_deletion_preview(pid)
    if preview is None:
        return None
    backup_path = await create_database_backup("advanced-project-delete")
    result: dict[str, object] = {**preview, "backup_path": str(backup_path)}
    if project_name != preview["project_name"]:
        return {**result, "ok": False, "code": "name_mismatch"}
    if preview["achievement_count"]:
        return {**result, "ok": False, "code": "achievements_present"}
    if not await delete_project(pid):
        return None
    return {**result, "ok": True, "code": "deleted"}


# 2026-07-30: 拖动 reorder
async def reorder_projects(items: list[dict]) -> int:
    """批量更新项目 sort_order。

    入参 items = [{id: str, sort_order: int}, ...], 来自前端 ProjectReorderRequest.items。
    存间隔 10 避免每改一项就更新全部行 — 一次拖动只发 1 项 sort_order, 这里
    也只 UPDATE 1 行, 不是全表。

    返回: 实际更新的行数。前端可用来判断哪些 id 不存在。
    """
    if not items:
        return 0
    async with get_session() as session:
        updated = 0
        for it in items:
            result = await session.execute(
                select(ProjectORM).where(ProjectORM.id == it["id"])
            )
            p = result.scalar_one_or_none()
            if p:
                p.sort_order = it["sort_order"]
                updated += 1
        await session.flush()
        return updated


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
        # 2026-07-30: 新加任务 sort_order = max+10 (项目内), 排在项目任务列表最后
        new_order = await _next_sort_order_for_project(session, data.project)
        task = TaskORM(
            id=_new_id("task"),
            project_id=data.project,
            title=data.title,
            description=data.description,
            status=TaskStatus.NOT_STARTED.value,
            priority=data.priority.value,
            due=data.due,
            blocked=data.blocked,
            created_at=date.today(),
            checklist_json=json.dumps(checklist_data, ensure_ascii=False),
            sort_order=new_order,
        )
        session.add(task)
        await session.flush()
        return _task_to_pydantic(task)


async def get_task(tid: str) -> Optional[Task]:
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        return _task_to_pydantic(t) if t else None


async def list_tasks(
    project_id: Optional[str] = None,
    include_completed: bool = False,
) -> list[Task]:
    """列项目下所有任务。

    2026-08-01: 默认隐藏 status=COMPLETED (task 保留但不在主列表里)。
    加 include_completed=True 拿全部 (前端"查看已完成 N" 折叠区用)。
    """
    async with get_session() as session:
        # 2026-07-30: 拖动排序, 跟 Project 同样 secondary created_at fallback
        stmt = select(TaskORM).order_by(TaskORM.sort_order.asc(), TaskORM.created_at.asc())
        if project_id:
            stmt = stmt.where(TaskORM.project_id == project_id)
        if not include_completed:
            stmt = stmt.where(TaskORM.status != TaskStatus.COMPLETED.value)
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
        # due 是 Optional[date]: None 是合法值 (语义 = "清空截止日期")。
        # 不能再用 `is not None` 判断 — 那样 PATCH {"due": null} 会被静默吞掉,
        # 用户没法从 UI 清掉已设的 due (2026-07-22 用户报)。
        # 改用 Pydantic v2 的 model_fields_set 区分"未传" vs "传了 None":
        #   - LLM 工具 / 前端 PATCH 显式传 null → "due" 在 model_fields_set → 清空
        #   - PATCH 不带 due 字段 → "due" 不在 model_fields_set → 不动
        # 端点级行为锁在 app/tests/test_api_patch_due_null.py
        if "due" in data.model_fields_set:
            t.due = data.due
        if data.blocked is not None:
            t.blocked = data.blocked
        if data.checklist is not None:
            checklist_data = [item.model_dump() if hasattr(item, "model_dump") else item
                              for item in data.checklist]
            t.checklist_json = json.dumps(checklist_data, ensure_ascii=False)
        await session.flush()
        return _task_to_pydantic(t)


async def delete_task(tid: str) -> bool:
    async with get_session() as session:
        result = await session.execute(select(TaskORM).where(TaskORM.id == tid))
        t = result.scalar_one_or_none()
        if not t:
            return False
        await session.delete(t)
        return True


# 2026-07-30: 拖动 reorder
async def reorder_tasks(items: list[dict]) -> int:
    """批量更新任务 sort_order。语义跟 reorder_projects 一样, 但**不能跨项目**。

    任务绑死在 project_id 下, 跨项目 reorder 没意义 (task 的 sort_order 是
    项目内局部顺序, 全局混排会让 list 排序乱套)。前端按项目分别 reorder, 这里
    校验所有 id 的 project_id 一致, 不一致返回 0 (不更新任何行, 由前端定位问题)。

    实际: 前端永远按项目分别 reorder, 这里校验是兜底, 防止 LLM 工具误调或脚本
    bug 把跨项目的 task sort_order 搞乱。
    """
    if not items:
        return 0
    async with get_session() as session:
        # 校验所有 id 的 project_id 一致
        ids = [it["id"] for it in items]
        result = await session.execute(
            select(TaskORM.project_id, TaskORM.id).where(TaskORM.id.in_(ids))
        )
        found = {row.id: row.project_id for row in result}
        project_ids = set(found.values())
        if len(project_ids) > 1:
            logger.warning(
                f"reorder_tasks 跨项目拒绝: 包含多个 project_id {project_ids}"
            )
            return 0
        # 批量更新
        updated = 0
        for it in items:
            t_id = it["id"]
            if t_id not in found:
                continue
            t_result = await session.execute(
                select(TaskORM).where(TaskORM.id == t_id)
            )
            t = t_result.scalar_one_or_none()
            if t:
                t.sort_order = it["sort_order"]
                updated += 1
        await session.flush()
        return updated


# ===== CRUD: Achievements =====


@dataclass(frozen=True)
class ReadinessDecision:
    """The storage-owned decision for whether an achievement may enter formal output."""

    status: CVStatus
    unmet_reasons: list[str]


def _provenance_guardrail(
    *,
    task_title: str,
    outcome: str,
    reflection: str,
    cv: str,
    answers: dict[str, str],
) -> dict[str, bool]:
    """Run the deterministic P0 fact guard against outcome plus structured answers."""
    answer_evidence = "\n".join(answer.strip() for answer in answers.values() if answer.strip())
    case = AchievementDistillationCase(
        id="runtime-readiness",
        category="boundary",
        severity="p0",
        input=AchievementDistillationInput(
            task_title=task_title,
            outcome="\n".join(part for part in [outcome.strip(), answer_evidence] if part),
            reflection=reflection.strip() or None,
            language="zh-CN",
        ),
    )
    checks = evaluate_l1(
        case,
        AchievementDistillationOutput(cv=cv, follow_up_questions=[], generator_status="polished"),
    )
    return {
        "has_unsupported_number": checks.has_unsupported_number,
        "has_unsupported_entity": checks.has_unsupported_entity,
        "ownership_violation": checks.ownership_violation,
    }


def derive_achievement_readiness(
    *,
    task_title: str,
    outcome: str,
    cv: str,
    requested_status: CVStatus,
    follow_up_questions: list[str],
    follow_up_answers: dict[str, str],
    final_cv_confirmed: bool,
    cv_regenerated_after_answers: bool,
    provenance: dict[str, bool],
) -> ReadinessDecision:
    """Derive report eligibility from evidence, never from a caller's ready claim."""
    if requested_status == CVStatus.PENDING:
        return ReadinessDecision(CVStatus.PENDING, ["用户选择暂存草稿"])

    reasons: list[str] = []
    questions = [question.strip() for question in follow_up_questions if question.strip()]
    is_title_fallback = cv.strip() == f"完成「{task_title}」"
    if len(outcome.strip()) < 10:
        reasons.append("缺少结果描述")
    if is_title_fallback:
        reasons.append("CV 仍是任务标题兜底")
    if any(not (follow_up_answers.get(str(index)) or "").strip() for index in range(len(questions))):
        reasons.append("追问未答")
    if questions and all((follow_up_answers.get(str(index)) or "").strip() for index in range(len(questions))):
        if not cv_regenerated_after_answers:
            reasons.append("CV 尚未吸收补充证据")
    if not final_cv_confirmed:
        reasons.append("CV 尚未确认")
    if any(provenance.values()):
        reasons.append("存在无来源事实")
    if reasons:
        return ReadinessDecision(CVStatus.NEEDS_DATA, reasons)
    return ReadinessDecision(CVStatus.READY, [])


async def complete_task(
    task_id: str,
    outcome: str = "",
    reflection: str = "",
    cv: str = "",
    cv_status: CVStatus = CVStatus.READY,
    follow_up_questions: Optional[list[str]] = None,
    follow_up_answers: Optional[dict[str, str]] = None,
    distillation_trace_id: Optional[str] = None,
    confirmed_cv: bool = False,
) -> Optional[Achievement]:
    """完成任务并沉淀为成就。

    2026-08-01 改造:
    1. task 不再删, 改 status=COMPLETED + completed_at=今天
       - 旧版 (v1-v3): task 删掉, 用户在看板找不到自己完成过的事
       - 新版 (v4): task 保留 (划掉 + 灰色), 用户能"看回"自己干的活
       - list_tasks 默认隐藏 COMPLETED, 加 include_completed=True 参数显示
       - 成就仍然 append (每次完成一条 task 写一行 Achievement, 多次完成同 task 多次 append)
       - 撤销走 undo_completion: 改 task.status 回 IN_PROGRESS + 删对应 achievement
    2. follow_up_questions (LLM 主动追问) 入库
       - 2026-08-01 立: LLM 完成任务后根据任务类型生成 1-3 个追问
         (e.g. "上线后 DAU 涨了多少?" / "用户反馈如何?")
       - 用户在 follow-up 页 (web/app/achievements/follow-up) 补全答案
       - 补全后 cv_status 升级 ready
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
        questions = [question.strip() for question in (follow_up_questions or []) if question.strip()]
        answers = {
            str(key): value.strip()
            for key, value in (follow_up_answers or {}).items()
            if isinstance(value, str) and value.strip()
        }
        readiness = derive_achievement_readiness(
            task_title=task.title,
            outcome=outcome,
            cv=cv,
            requested_status=cv_status,
            follow_up_questions=questions,
            follow_up_answers=answers,
            final_cv_confirmed=confirmed_cv,
            cv_regenerated_after_answers=not questions,
            provenance=_provenance_guardrail(
                task_title=task.title, outcome=outcome, reflection=reflection, cv=cv, answers=answers,
            ),
        )
        # 写 achievement (append, 多次完成同 task 多次 append)
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
            cv_status=readiness.status.value,
            tags_json="[]",
            follow_up_questions_json=json.dumps(questions, ensure_ascii=False),
            follow_up_answers_json=json.dumps(answers, ensure_ascii=False),
            distillation_trace_id=distillation_trace_id,
        )
        session.add(achievement)
        if distillation_trace_id and readiness.status == CVStatus.PENDING:
            from app.harness.feedback import record_confirmation_feedback_in_session

            await record_confirmation_feedback_in_session(
                session,
                trace_id=distillation_trace_id,
                original_cv=cv,
                final_cv=cv,
                action="draft",
            )
        elif distillation_trace_id and confirmed_cv:
            from app.harness.feedback import record_confirmation_feedback_in_session

            await record_confirmation_feedback_in_session(
                session,
                trace_id=distillation_trace_id,
                original_cv=cv,
                final_cv=cv,
                action="confirmed",
            )
        # 2026-08-01: 改 task 状态 (不删), 保留"看回" 体验
        task.status = TaskStatus.COMPLETED.value
        task.completed_at = date.today()
        await session.flush()
        return _achievement_to_pydantic(achievement, unmet_reasons=readiness.unmet_reasons)


async def update_achievement_cv(aid: str, data: AchievementUpdate) -> Optional[Achievement]:
    async with get_session() as session:
        result = await session.execute(select(AchievementORM).where(AchievementORM.id == aid))
        a = result.scalar_one_or_none()
        if not a:
            return None
        decision: ReadinessDecision | None = None
        if data.cv is not None:
            original_cv = a.cv
            a.cv = data.cv
            questions = json.loads(a.follow_up_questions_json or "[]")
            answers = json.loads(a.follow_up_answers_json or "{}")
            was_ready = a.cv_status == CVStatus.READY.value
            decision = derive_achievement_readiness(
                task_title=a.title,
                outcome=a.outcome,
                cv=a.cv,
                requested_status=CVStatus(a.cv_status),
                follow_up_questions=questions,
                follow_up_answers=answers,
                final_cv_confirmed=was_ready,
                cv_regenerated_after_answers=a.cv.strip() != original_cv.strip(),
                provenance=_provenance_guardrail(
                    task_title=a.title,
                    outcome=a.outcome,
                    reflection=a.reflection,
                    cv=a.cv,
                    answers=answers,
                ),
            )
            a.cv_status = decision.status.value
            if a.distillation_trace_id and data.cv != original_cv:
                try:
                    from app.harness.feedback import record_feedback

                    await record_feedback(a.distillation_trace_id, original_cv, data.cv)
                except Exception as feedback_error:
                    logger.warning("achievement feedback persistence failed: %s", feedback_error)
        await session.flush()
        return _achievement_to_pydantic(a, unmet_reasons=decision.unmet_reasons if decision else None)


async def answer_follow_ups(aid: str, answers: dict) -> Optional[Achievement]:
    """补全追问 (2026-08-01 立)。

    流程:
    1. 写 follow_up_answers 到 achievement
    2. cv_status 自动升级 ready (用户主动补全了 = 数据够用)

    返回更新后的 Achievement。
    """
    async with get_session() as session:
        result = await session.execute(select(AchievementORM).where(AchievementORM.id == aid))
        a = result.scalar_one_or_none()
        if not a:
            return None
        # 合并新答案 (旧答案 + 新答案, 新覆盖旧)
        existing = json.loads(a.follow_up_answers_json or "{}")
        existing.update({
            str(key): value.strip()
            for key, value in answers.items()
            if isinstance(value, str) and value.strip()
        })
        a.follow_up_answers_json = json.dumps(existing, ensure_ascii=False)
        questions = json.loads(a.follow_up_questions_json or "[]")
        decision = derive_achievement_readiness(
            task_title=a.title,
            outcome=a.outcome,
            cv=a.cv,
            requested_status=CVStatus(a.cv_status),
            follow_up_questions=questions,
            follow_up_answers=existing,
            final_cv_confirmed=False,
            cv_regenerated_after_answers=False,
            provenance=_provenance_guardrail(
                task_title=a.title,
                outcome=a.outcome,
                reflection=a.reflection,
                cv=a.cv,
                answers=existing,
            ),
        )
        if a.cv_status != CVStatus.PENDING.value:
            a.cv_status = CVStatus.NEEDS_DATA.value
        await session.flush()
        return _achievement_to_pydantic(a, unmet_reasons=decision.unmet_reasons)


async def resolve_achievement(
    aid: str,
    *,
    answers: dict[str, str],
    cv: str,
    distillation_trace_id: Optional[str] = None,
) -> Optional[Achievement]:
    """Atomically save evidence and a user-confirmed regenerated CV."""
    async with get_session() as session:
        result = await session.execute(select(AchievementORM).where(AchievementORM.id == aid))
        achievement = result.scalar_one_or_none()
        if not achievement:
            return None

        existing_answers = json.loads(achievement.follow_up_answers_json or "{}")
        existing_answers.update({
            str(key): value.strip()
            for key, value in answers.items()
            if isinstance(value, str) and value.strip()
        })
        questions = json.loads(achievement.follow_up_questions_json or "[]")
        previous_cv = achievement.cv
        decision = derive_achievement_readiness(
            task_title=achievement.title,
            outcome=achievement.outcome,
            cv=cv,
            requested_status=CVStatus.NEEDS_DATA,
            follow_up_questions=questions,
            follow_up_answers=existing_answers,
            final_cv_confirmed=True,
            cv_regenerated_after_answers=cv.strip() != previous_cv.strip(),
            provenance=_provenance_guardrail(
                task_title=achievement.title,
                outcome=achievement.outcome,
                reflection=achievement.reflection,
                cv=cv,
                answers=existing_answers,
            ),
        )
        achievement.follow_up_answers_json = json.dumps(existing_answers, ensure_ascii=False)
        achievement.cv = cv.strip()
        achievement.cv_status = decision.status.value
        if distillation_trace_id:
            achievement.distillation_trace_id = distillation_trace_id
        trace_id = achievement.distillation_trace_id
        if trace_id:
            from app.harness.feedback import record_confirmation_feedback_in_session

            await record_confirmation_feedback_in_session(
                session,
                trace_id=trace_id,
                original_cv=previous_cv,
                final_cv=achievement.cv,
                action="confirmed",
            )
        await session.flush()
        return _achievement_to_pydantic(achievement, unmet_reasons=decision.unmet_reasons)


async def list_achievements(
    project_name: Optional[str] = None,
    since: Optional[date] = None,
    only_ready: bool = False,
    cv_status: Optional[CVStatus] = None,
) -> list[Achievement]:
    async with get_session() as session:
        stmt = select(AchievementORM).order_by(AchievementORM.date.desc())
        if project_name:
            stmt = stmt.where(AchievementORM.project == project_name)
        if since:
            stmt = stmt.where(AchievementORM.date >= since)
        if cv_status is not None:
            # 精确状态过滤（2026-07-20 立 needs_data 后, 比 only_ready 更灵活）
            stmt = stmt.where(AchievementORM.cv_status == cv_status.value)
        elif only_ready:
            # 兼容旧 API: only_ready=true 仍走 ready
            stmt = stmt.where(AchievementORM.cv_status == CVStatus.READY.value)
        result = await session.execute(stmt)
        return [_achievement_to_pydantic(a) for a in result.scalars()]


async def list_output_ready_achievements(
    *,
    project_name: Optional[str] = None,
    since: Optional[date] = None,
) -> list[Achievement]:
    """The sole read boundary for formal reports and other career outputs."""
    async with get_session() as session:
        stmt = (
            select(AchievementORM)
            .where(AchievementORM.cv_status == CVStatus.READY.value)
            .order_by(AchievementORM.date.desc())
        )
        if project_name:
            stmt = stmt.where(AchievementORM.project == project_name)
        if since:
            stmt = stmt.where(AchievementORM.date >= since)
        result = await session.execute(stmt)
        return [_achievement_to_pydantic(a) for a in result.scalars()]


async def undo_completion(aid: str) -> Optional[Task]:
    """撤销完成：恢复 task 状态，删除 achievement。

    2026-08-01 改造: task 不删, 撤销改成"改 task.status 回去"。
    - 旧版 (v1-v3): 删 task, 撤销时用 achievement.task_id 重建 task (priority/checklist 都丢)
    - 新版 (v4): task 一直存在, 撤销只改 status (priority/checklist 保留)
    - 多次完成同 task 多次 append achievement, 撤销只删最新一条
    """
    async with get_session() as session:
        result = await session.execute(select(AchievementORM).where(AchievementORM.id == aid))
        achievement = result.scalar_one_or_none()
        if not achievement:
            return None
        # 找对应 task (新版: task 还在, 状态=COMPLETED)
        task_result = await session.execute(
            select(TaskORM).where(TaskORM.id == achievement.task_id)
        )
        task = task_result.scalar_one_or_none()
        if not task:
            # 旧数据兼容: task 已被删 (2026-08-01 之前的 achievement)
            # 走旧路径重建 task
            proj_result = await session.execute(
                select(ProjectORM).where(ProjectORM.id == achievement.project_id)
            )
            if not proj_result.scalar_one_or_none():
                raise ValueError(f"Project {achievement.project_id} not found")
            task = TaskORM(
                id=achievement.task_id,
                project_id=achievement.project_id,
                title=achievement.title,
                status=TaskStatus.IN_PROGRESS.value,
                priority=Priority.P2.value,
                due=None,
                blocked=False,
                created_at=date.today(),
                completed_at=None,
                checklist_json="[]",
            )
            session.add(task)
        else:
            # 新路径: 改 status 回去 (保留 priority/checklist/created_at 等)
            task.status = TaskStatus.IN_PROGRESS.value
            task.completed_at = None
        await session.flush()
        # 删 achievement
        await session.delete(achievement)
        return _task_to_pydantic(task)


async def undo_by_task_id(task_id: str) -> Optional[Task]:
    """按 task_id 撤销最近一次完成（2026-08-01 立）。

    用途: 主页"已完成 task" 折叠区的撤销按钮 — 用户看到 task (不是 achievement) 想撤销,
    按 task_id 找该 task 对应的最新一条 achievement 调 undo_completion。

    多次完成同 task 多次 append achievement, 撤销只删最新一条 (跟 undo_completion 一致)。
    """
    async with get_session() as session:
        # 找该 task_id 对应的最新一条 achievement (按 date desc)
        ach_result = await session.execute(
            select(AchievementORM)
            .where(AchievementORM.task_id == task_id)
            .order_by(AchievementORM.date.desc())
        )
        latest = ach_result.scalars().first()
        if not latest:
            return None
        # 用 id 调既有 undo_completion
        return await undo_completion(latest.id)


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
        # 2026-07-30: 拖动排序。snapshot 也按 sort_order ASC 排, 跟 list 端点对齐
        proj_result = await session.execute(
            select(ProjectORM).order_by(ProjectORM.sort_order.asc(), ProjectORM.created_at.asc())
        )
        all_projects = proj_result.scalars().all()

        # task 全表扫, 下面按 project 分组时再按 sort_order 排
        task_result = await session.execute(
            select(TaskORM).order_by(TaskORM.sort_order.asc(), TaskORM.created_at.asc())
        )
        all_tasks = [_task_to_pydantic(t) for t in task_result.scalars().all()]

        today = date.today()
        ach_result = await session.execute(
            select(AchievementORM).where(AchievementORM.date == today)
        )
        done_today = [_achievement_to_pydantic(a) for a in ach_result.scalars().all()]

        all_ach_result = await session.execute(select(AchievementORM))
        all_achievements = all_ach_result.scalars().all()
        ready_count = sum(1 for a in all_achievements if a.cv_status == CVStatus.READY.value)
        needs_data_count = sum(1 for a in all_achievements if a.cv_status == CVStatus.NEEDS_DATA.value)
        pending_count = sum(1 for a in all_achievements if a.cv_status == CVStatus.PENDING.value)

    # 2026-08-01: 区分 active vs done, focus/projects_grouped 只放 active (任务流干净)
    active_tasks = [t for t in all_tasks if t.status != TaskStatus.COMPLETED.value]
    done_tasks = [t for t in all_tasks if t.status == TaskStatus.COMPLETED.value]

    # 2026-08-13: 项目内已完成任务按 completed_at desc 排, 同时间用 sort_order + id 兜底保稳定
    def completed_task_sort_key(task: Task) -> tuple[int, int, str]:
        completed = task.completed_at or date.min
        return (-completed.toordinal(), task.sort_order, task.id)

    # 算 focus (只看 active, 用户最该被聚焦的是"还没完成的")
    focus_tasks = sort_focus(active_tasks)[:5]
    focus = [
        FocusItem(
            id=t.id,
            project=t.project,
            title=t.title,
            priority=t.priority,
            due=t.due,
            blocked=t.blocked,
        )
        for t in focus_tasks
    ]

    # 按 project 分组 (active only, 算 done_count 给前端"查看已完成 N" 折叠区)
    known_pids = {p.id for p in all_projects}
    projects_grouped: list[ProjectSnapshot] = []
    for p in all_projects:
        if p.archived:
            continue
        p_active = [t for t in active_tasks if t.project == p.id]
        # 2026-08-13: 已完成列表按 completed_at desc 排序, 跟 done_count 计数同源
        p_done = sorted(
            (t for t in done_tasks if t.project == p.id),
            key=completed_task_sort_key,
        )
        projects_grouped.append(ProjectSnapshot(
            id=p.id, name=p.name, description=p.description, tasks=p_active,
            done_tasks=p_done,
            done_count=len(p_done),
            sort_order=p.sort_order,  # 2026-07-30: 透传 sort_order 给前端
            emoji=p.emoji,  # 2026-08-11: 透传 emoji, 不传前端显示就跟用户选的对不上
        ))

    # 未分组的 task (孤儿, project 已被删/不存在)。sort_order 用 0 兜底
    orphans = [t for t in active_tasks if t.project not in known_pids]
    if orphans:
        projects_grouped.append(ProjectSnapshot(
            id=None, name="未分组", tasks=orphans, done_tasks=[], done_count=0, sort_order=0,
            emoji=None,  # 未分组没用 emoji, 走 📁 兜底
        ))

    return Snapshot(
        focus=focus,
        projects=projects_grouped,
        done_today=done_today,
        # 2026-08-01: 全局已完成 task 列表 (按 completed_at desc 排, 最近完成的在前)
        done_tasks=sorted(done_tasks, key=lambda t: t.completed_at or date.min, reverse=True),
        counts={
            "achievementsReady": ready_count,
            "achievementsNeedsData": needs_data_count,
            "achievementsPending": pending_count,
            "achievementsNeedsAttention": needs_data_count + pending_count,
        },
    )
