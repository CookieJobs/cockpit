"""Dataset loader for achievement distillation harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.harness.models import AchievementDistillationCase, dataset_path


def _load_raw_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return data


def load_cases(path: str | Path | None = None) -> list[AchievementDistillationCase]:
    path = Path(path) if path is not None else dataset_path()
    raw_cases = _load_raw_cases(path)
    cases: list[AchievementDistillationCase] = []

    for index, raw_case in enumerate(raw_cases):
        case_id = raw_case.get("id", f"index_{index}") if isinstance(raw_case, dict) else f"index_{index}"
        try:
            cases.append(AchievementDistillationCase.model_validate(raw_case))
        except ValidationError as exc:
            raise ValueError(
                f"Malformed achievement distillation case {case_id!r} at index {index}: {exc}"
            ) from exc

    return cases


__all__ = ["load_cases"]
