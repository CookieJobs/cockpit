"""Loading helpers for the versioned synthetic dogfooding dataset."""

from __future__ import annotations

import json
from pathlib import Path

from app.harness.synthetic.models import SyntheticDataset


def dataset_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_dogfooding_v1.json"


def load_synthetic_dataset(path: Path | None = None) -> SyntheticDataset:
    with (path or dataset_path()).open(encoding="utf-8") as fixture_file:
        return SyntheticDataset.model_validate(json.load(fixture_file))
