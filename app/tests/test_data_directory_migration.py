"""Regression tests for local data directory resolution and recovery."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from app.core import storage
from app.core.config import DataRecoveryRequired, Settings, migrate_misplaced_database, settings
from app.core.models import ProjectCreate
from app.main import health


def _create_sqlite_database(path: Path, marker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker(value) VALUES (?)", (marker,))
        connection.commit()


def _database_marker(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM marker").fetchone()[0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_data_dir_expands_home_before_constructing_database_url(monkeypatch, tmp_path):
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("COCKPIT_DATA_DIR", "~/.cockpit")

    settings = Settings(_env_file=None)

    assert settings.resolved_data_dir() == home / ".cockpit"
    assert settings.get_database_url() == f"sqlite+aiosqlite:///{home / '.cockpit' / 'cockpit.db'}"
    assert not (tmp_path / "~" / ".cockpit").exists()


def test_only_misplaced_database_is_copied_verified_and_retained(tmp_path):
    cwd = tmp_path / "workspace"
    misplaced = cwd / "~" / ".cockpit" / "cockpit.db"
    correct = tmp_path / "home" / ".cockpit" / "cockpit.db"
    _create_sqlite_database(misplaced, "legacy-working-data")

    state = migrate_misplaced_database(cwd=cwd, target=correct)

    assert state.kind == "migrated"
    assert _database_marker(correct) == "legacy-working-data"
    assert misplaced.exists()
    assert list(misplaced.parent.glob("cockpit.db.migrated-*.bak"))


def test_equal_databases_use_correct_location_without_overwriting_either(tmp_path):
    cwd = tmp_path / "workspace"
    misplaced = cwd / "~" / ".cockpit" / "cockpit.db"
    correct = tmp_path / "home" / ".cockpit" / "cockpit.db"
    _create_sqlite_database(misplaced, "same-data")
    correct.parent.mkdir(parents=True, exist_ok=True)
    correct.write_bytes(misplaced.read_bytes())
    before = (_sha256(misplaced), _sha256(correct))

    state = migrate_misplaced_database(cwd=cwd, target=correct)

    assert state.kind == "already_migrated"
    assert (_sha256(misplaced), _sha256(correct)) == before


def test_different_databases_enter_conflict_without_touching_either(tmp_path):
    cwd = tmp_path / "workspace"
    misplaced = cwd / "~" / ".cockpit" / "cockpit.db"
    correct = tmp_path / "home" / ".cockpit" / "cockpit.db"
    _create_sqlite_database(misplaced, "misplaced-data")
    _create_sqlite_database(correct, "correct-data")
    before = (_sha256(misplaced), _sha256(correct))

    state = migrate_misplaced_database(cwd=cwd, target=correct)

    assert state.kind == "conflict"
    assert state.message
    assert (_sha256(misplaced), _sha256(correct)) == before


def test_conflict_keeps_the_correct_database_readable_for_recovery(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("COCKPIT_DATA_DIR", "~/.cockpit")
    _create_sqlite_database(workspace / "~" / ".cockpit" / "cockpit.db", "misplaced-data")
    _create_sqlite_database(home / ".cockpit" / "cockpit.db", "correct-data")

    configured = Settings(_env_file=None)

    assert configured.get_database_url() == f"sqlite+aiosqlite:///{home / '.cockpit' / 'cockpit.db'}"
    assert configured.data_recovery_state().kind == "conflict"


@pytest.mark.asyncio
async def test_conflict_blocks_storage_writes_but_not_read_sessions(temp_db, monkeypatch, tmp_path):
    state = migrate_misplaced_database(
        cwd=tmp_path / "workspace",
        target=tmp_path / "home" / ".cockpit" / "cockpit.db",
    )
    conflict = state.__class__(
        kind="conflict",
        target=state.target,
        misplaced=state.misplaced,
        message="请选择主库后再继续写入。",
    )
    monkeypatch.setattr(settings, "_data_recovery_state", conflict)

    async with storage.get_session() as session:
        await session.execute(storage.select(storage.ProjectORM))

    with pytest.raises(DataRecoveryRequired):
        await storage.add_project(ProjectCreate(name="必须暂停的写入"))


@pytest.mark.asyncio
async def test_health_exposes_actionable_data_recovery_state(monkeypatch, tmp_path):
    state = migrate_misplaced_database(
        cwd=tmp_path / "workspace",
        target=tmp_path / "home" / ".cockpit" / "cockpit.db",
    )
    conflict = state.__class__(
        kind="conflict",
        target=state.target,
        misplaced=state.misplaced,
        message="请选择主库后再继续写入。",
    )
    monkeypatch.setattr(settings, "_data_recovery_state", conflict)

    response = await health()

    assert response["data_recovery"]["kind"] == "conflict"
    assert response["data_recovery"]["message"] == "请选择主库后再继续写入。"
