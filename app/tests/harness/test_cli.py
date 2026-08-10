from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_fake_fixture_cli_writes_stable_report(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    result = subprocess.run(  # noqa: S603
        [
            ".venv312/bin/python",
            "app/scripts/run_achievement_harness.py",
            "--fake-fixture",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total"] == 30
    assert set(report["by_category"]) == {"golden", "boundary", "adversarial"}
    assert report["generator_status_counts"] == {"polished": 30}


def test_gate_cli_returns_nonzero_with_blocking_reasons() -> None:
    result = subprocess.run(  # noqa: S603
        [
            ".venv312/bin/python",
            "app/scripts/run_achievement_harness.py",
            "--fake-fixture",
            "--gate",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "gate" in payload
    assert "semantic_average" in payload["gate"]["blocking_reasons"]


def test_cli_can_run_current_baseline_suite_only(tmp_path: Path) -> None:
    output = tmp_path / "current.json"
    result = subprocess.run(  # noqa: S603
        [
            ".venv312/bin/python",
            "app/scripts/run_achievement_harness.py",
            "--fake-fixture",
            "--suite",
            "current_baseline",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["total"] == 19
