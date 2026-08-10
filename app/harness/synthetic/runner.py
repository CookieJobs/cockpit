"""Replay synthetic work through Cockpit's public HTTP API boundary."""

from __future__ import annotations

import asyncio
import json
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient

from app.core import storage
from app.harness.synthetic.fixtures import load_synthetic_dataset
from app.harness.synthetic.models import Persona, WorkEvent
from app.main import app


@dataclass(frozen=True)
class PersonaReplay:
    persona_id: str
    achievements: list[dict]
    database_isolated: bool = True


@dataclass(frozen=True)
class SyntheticReplay:
    personas: list[PersonaReplay]
    synthetic: bool = True
    database_location: str = "temporary and discarded"


@contextmanager
def _fixture_completion_date(completed_on: date) -> Iterator[None]:
    """Freeze only the storage module's completion date during synthetic replay."""
    original_date = storage.date

    class FixtureDate(date):
        @classmethod
        def today(cls) -> date:
            return completed_on

    storage.date = FixtureDate
    try:
        yield
    finally:
        storage.date = original_date


def _replay_persona(persona: Persona, events: list[WorkEvent]) -> PersonaReplay:
    """Use a one-off SQLite database and HTTP endpoints for one persona only."""
    with tempfile.NamedTemporaryFile(prefix=f"cockpit-{persona.id}-", suffix=".db") as database_file:
        database_url = f"sqlite+aiosqlite:///{database_file.name}"
        storage.reset_engine()
        storage.init_engine(database_url=database_url)
        asyncio.run(storage.create_tables())
        try:
            client = TestClient(app)
            project_ids: dict[str, str] = {}
            for event in sorted(events, key=lambda item: item.completed_on):
                project_id = project_ids.get(event.project_name)
                if project_id is None:
                    project_response = client.post(
                        "/api/projects",
                        json={"name": event.project_name, "description": persona.work_context},
                    )
                    project_response.raise_for_status()
                    project_id = project_response.json()["id"]
                    project_ids[event.project_name] = project_id

                task_response = client.post(
                    "/api/tasks",
                    json={"project": project_id, "title": event.task_title},
                )
                task_response.raise_for_status()
                with _fixture_completion_date(event.completed_on):
                    completion_response = client.post(
                        f"/api/tasks/{task_response.json()['id']}/complete",
                        json={
                            "outcome": event.outcome,
                            "cv": event.cv,
                            "reflection": event.reflection or "",
                            "cv_status": event.expected_readiness,
                            "follow_up_questions": event.follow_up_questions,
                        },
                    )
                completion_response.raise_for_status()
                achievement = completion_response.json()
                if achievement["cv_status"] != event.expected_readiness:
                    raise RuntimeError(
                        f"{event.id}: expected {event.expected_readiness}, got {achievement['cv_status']}"
                    )

            achievements_response = client.get("/api/achievements")
            achievements_response.raise_for_status()
            return PersonaReplay(persona_id=persona.id, achievements=achievements_response.json())
        finally:
            storage.reset_engine()


def run_synthetic_dogfooding(*, output_dir: Path) -> SyntheticReplay:
    """Replay every v1 persona without ever opening the live Cockpit database."""
    resolved_output = output_dir.resolve()
    live_data_dir = (Path.home() / ".cockpit").resolve()
    if resolved_output == live_data_dir or live_data_dir in resolved_output.parents:
        raise ValueError("synthetic dogfooding output must not be written under ~/.cockpit")
    resolved_output.mkdir(parents=True, exist_ok=True)

    dataset = load_synthetic_dataset()
    replays = [
        _replay_persona(
            persona,
            [event for event in dataset.events if event.persona_id == persona.id],
        )
        for persona in dataset.personas
    ]
    replay = SyntheticReplay(personas=replays)
    (resolved_output / "replay.json").write_text(
        json.dumps(asdict(replay), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return replay
