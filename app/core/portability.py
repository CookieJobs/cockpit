"""Local, versioned career-memory export and conservative import boundary."""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, select

from app.core import storage


ARCHIVE_FORMAT = "cockpit-career-memory"
SCHEMA_VERSION = 1
_TABLES = (
    ("projects", storage.ProjectORM),
    ("tasks", storage.TaskORM),
    ("achievements", storage.AchievementORM),
    ("chat_sessions", storage.ChatSessionORM),
    ("chat_messages", storage.ChatMessageORM),
    ("distillation_traces", storage.DistillationTraceORM),
    ("distillation_feedback", storage.DistillationFeedbackORM),
)
_TABLE_BY_NAME = dict(_TABLES)


class ArchiveValidationError(ValueError):
    """Archive is malformed, unsupported, or unsafe to merge."""


class ImportConfirmationRequired(ValueError):
    """Import is destructive enough to require an explicit confirmation."""


@dataclass(frozen=True)
class ImportPreview:
    schema_version: int
    counts: dict[str, int]
    conflicts: dict[str, list[str]]


@dataclass(frozen=True)
class ImportResult:
    imported_counts: dict[str, int]
    backup_path: str


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {column.name: _json_value(getattr(row, column.name)) for column in row.__table__.columns}


def _decode_row(model: Any, row: dict[str, Any]) -> dict[str, Any]:
    columns = {column.name: column for column in model.__table__.columns}
    if set(row) != set(columns):
        raise ArchiveValidationError(f"invalid columns for {model.__tablename__}")
    decoded: dict[str, Any] = {}
    for name, value in row.items():
        column = columns[name]
        if isinstance(column.type, DateTime) and isinstance(value, str):
            decoded[name] = datetime.fromisoformat(value)
        elif isinstance(column.type, Date) and isinstance(value, str):
            decoded[name] = date.fromisoformat(value)
        else:
            decoded[name] = value
    return decoded


def _read_archive(archive: bytes) -> dict[str, list[dict[str, Any]]]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            if set(zipped.namelist()) != {"manifest.json", "data.json"}:
                raise ArchiveValidationError("archive must contain only manifest.json and data.json")
            if sum(info.file_size for info in zipped.infolist()) > 25 * 1024 * 1024:
                raise ArchiveValidationError("archive is too large")
            manifest = json.loads(zipped.read("manifest.json"))
            data = json.loads(zipped.read("data.json"))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as exc:
        raise ArchiveValidationError("invalid Cockpit archive") from exc
    if not isinstance(manifest, dict) or manifest.get("format") != ARCHIVE_FORMAT:
        raise ArchiveValidationError("unsupported archive format")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ArchiveValidationError("unsupported archive schema version")
    if not isinstance(data, dict) or set(data) != set(_TABLE_BY_NAME):
        raise ArchiveValidationError("archive data tables do not match schema")
    for table, rows in data.items():
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ArchiveValidationError(f"invalid rows for {table}")
        # Validate every field before opening the import write transaction.
        for row in rows:
            _decode_row(_TABLE_BY_NAME[table], row)
    return data


async def _conflicts(data: dict[str, list[dict[str, Any]]]) -> dict[str, list[str]]:
    conflicts: dict[str, list[str]] = {}
    async with storage.get_session() as session:
        for table, model in _TABLES:
            ids = [row.get("id") for row in data[table]]
            if not all(isinstance(item, str) and item for item in ids):
                raise ArchiveValidationError(f"invalid id in {table}")
            if len(set(ids)) != len(ids):
                raise ArchiveValidationError(f"duplicate id in {table}")
            if not ids:
                conflicts[table] = []
                continue
            result = await session.execute(select(model.id).where(model.id.in_(ids)))
            conflicts[table] = sorted(result.scalars().all())
    return conflicts


async def export_archive() -> bytes:
    """Export career-memory rows only; settings and credentials never leave the DB."""
    data: dict[str, list[dict[str, Any]]] = {}
    async with storage.get_session() as session:
        for table, model in _TABLES:
            result = await session.execute(select(model).order_by(model.id.asc()))
            data[table] = [_row_to_dict(row) for row in result.scalars()]
    manifest = {
        "format": ARCHIVE_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(),
        "counts": {table: len(rows) for table, rows in data.items()},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        zipped.writestr("data.json", json.dumps(data, ensure_ascii=False, sort_keys=True))
    return buffer.getvalue()


async def preview_archive(archive: bytes) -> ImportPreview:
    """Validate an archive and list ID collisions without changing local state."""
    data = _read_archive(archive)
    return ImportPreview(
        schema_version=SCHEMA_VERSION,
        counts={table: len(rows) for table, rows in data.items()},
        conflicts=await _conflicts(data),
    )


async def import_archive(archive: bytes, *, confirmed: bool) -> ImportResult:
    """Backup first, then atomically import only if all IDs are collision-free."""
    if not confirmed:
        raise ImportConfirmationRequired("import requires explicit confirmation")
    backup_path = await storage.create_database_backup("import")
    data = _read_archive(archive)
    conflicts = await _conflicts(data)
    if any(conflicts.values()):
        raise ArchiveValidationError("ID collision: import does not merge or overwrite existing data")

    # get_session commits exactly once on success and rolls back every inserted row on failure.
    async with storage.get_session() as session:
        for table, model in _TABLES:
            session.add_all(model(**_decode_row(model, row)) for row in data[table])
        await session.flush()
    return ImportResult(
        imported_counts={table: len(rows) for table, rows in data.items()},
        backup_path=str(backup_path),
    )


# Public names intentionally state the Cockpit-only contract; short aliases remain
# internal-call compatible while external callers use the explicit functions.
export_cockpit_data = export_archive
preview_cockpit_import = preview_archive
import_cockpit_data = import_archive
