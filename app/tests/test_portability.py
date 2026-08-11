"""Versioned local export/import preserves the career-memory source of truth."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.main import app
from app.core.portability import (
    ArchiveValidationError,
    ImportConfirmationRequired,
    export_archive,
    import_archive,
    preview_archive,
)


async def _seed_all_portable_entities() -> None:
    """Seed every portable table without copying settings/secrets."""
    async with storage.get_session() as session:
        session.add_all([
            storage.ProjectORM(id="proj_portable", name="迁移项目", description="项目上下文", archived=False, sort_order=0),
            storage.TaskORM(
                id="task_portable", project_id="proj_portable", title="迁移任务",
                description="任务上下文", status="进行中", priority="P1", due=date(2026, 8, 10),
                blocked=False, completed_at=None, checklist_json='[{"text":"核验","done":false}]', sort_order=0,
            ),
            storage.AchievementORM(
                id="done_portable", date=date(2026, 8, 10), task_id="task_portable",
                project_id="proj_portable", project="迁移项目", title="迁移任务", outcome="完成迁移",
                reflection="保留反思", cv="主导迁移，完成验证", cv_status="ready", tags_json='["历史标签"]',
                follow_up_questions_json='["规模？"]', follow_up_answers_json='{"0":"10 项"}',
                distillation_trace_id="trace_portable",
            ),
            storage.ChatSessionORM(
                id="session_portable", label="迁移对话", archived=False,
                created_at=datetime(2026, 8, 10, 9), last_active_at=datetime(2026, 8, 10, 10),
            ),
            storage.ChatMessageORM(
                id="message_portable", session_id="session_portable", role="user", content='[{"type":"text","text":"你好"}]',
                tool_calls_json=None, created_at=datetime(2026, 8, 10, 9, 1),
            ),
            storage.DistillationTraceORM(
                id="trace_portable", task_id="task_portable", task_title="迁移任务", input_hash="hash",
                input_json="{}", raw_output="", parsed_output_json="{}", generator_status="fallback",
                guardrail_results_json="{}", final_quality_status="ready", model_version="local",
                prompt_version="v1", dataset_version="v1", harness_version="v1", latency_ms=1, error=None,
                created_at=datetime(2026, 8, 10, 9, 2),
            ),
            storage.DistillationFeedbackORM(
                id="feedback_portable", trace_id="trace_portable", original_cv="原文", final_cv="修订文",
                edit_type="confirmed", diff_json="{}", created_at=datetime(2026, 8, 10, 9, 3),
            ),
            storage.SettingsORM(key="llm_config", value='{"api_key":"must-not-export"}'),
        ])


@pytest.mark.asyncio
async def test_export_is_versioned_and_preserves_all_portable_rows_without_settings(temp_db):
    await _seed_all_portable_entities()

    archive = await export_archive()

    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
        data = json.loads(zipped.read("data.json"))
    assert manifest["schema_version"] == 1
    assert manifest["format"] == "cockpit-career-memory"
    assert data["achievements"][0]["tags_json"] == '["历史标签"]'
    assert set(data) == {
        "projects", "tasks", "achievements", "chat_sessions", "chat_messages",
        "distillation_traces", "distillation_feedback",
    }
    assert "settings" not in data


@pytest.mark.asyncio
async def test_preview_and_confirmed_import_restore_all_entities_and_reject_collisions(temp_db):
    await _seed_all_portable_entities()
    archive = await export_archive()

    preview = await preview_archive(archive)
    assert preview.schema_version == 1
    assert preview.counts == {"projects": 1, "tasks": 1, "achievements": 1, "chat_sessions": 1, "chat_messages": 1, "distillation_traces": 1, "distillation_feedback": 1}
    assert preview.conflicts["projects"] == ["proj_portable"]

    with pytest.raises(ImportConfirmationRequired):
        await import_archive(archive, confirmed=False)
    with pytest.raises(ArchiveValidationError, match="collision"):
        await import_archive(archive, confirmed=True)

    await storage.drop_tables()
    await storage.create_tables()
    preview_on_empty_db = await preview_archive(archive)
    assert not any(preview_on_empty_db.conflicts.values())
    result = await import_archive(archive, confirmed=True)
    assert result.imported_counts == preview.counts
    assert (await storage.list_projects())[0].description == "项目上下文"
    assert (await storage.list_achievements())[0].id == "done_portable"
    async with storage.get_session() as session:
        assert (await session.get(storage.ChatMessageORM, "message_portable")) is not None
        assert (await session.get(storage.DistillationFeedbackORM, "feedback_portable")) is not None


@pytest.mark.asyncio
async def test_invalid_archive_creates_recoverable_backup_and_writes_nothing(temp_db):
    db_path = Path(temp_db.removeprefix("sqlite+aiosqlite:///"))
    await _seed_all_portable_entities()

    with pytest.raises(ArchiveValidationError):
        await import_archive(b"not a zip", confirmed=True)

    assert list(db_path.parent.glob(f"{db_path.stem}.before-import-*.db"))
    assert (await storage.list_projects())[0].id == "proj_portable"


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_portability_endpoints_export_preview_and_require_explicit_confirmation(client):
    await _seed_all_portable_entities()

    exported = client.get("/api/backup/export")
    assert exported.status_code == 200
    assert b"must-not-export" not in exported.content
    preview = client.post(
        "/api/backup/import/preview",
        files={"file": ("career-memory.zip", exported.content, "application/zip")},
    )
    assert preview.status_code == 200
    assert preview.json()["counts"]["achievements"] == 1
    rejected = client.post(
        "/api/backup/import",
        files={"file": ("career-memory.zip", exported.content, "application/zip")},
        data={"confirmed": "false"},
    )
    assert rejected.status_code == 400
