from pathlib import Path

import pytest

from app.harness.capabilities import load_capabilities


def test_default_registry_has_unique_capability_ids() -> None:
    capabilities = load_capabilities()

    assert {item.id for item in capabilities} == {
        "achievement_distillation",
        "report_composition",
        "mcp_write_path",
        "constitution",
        "synthetic_dogfooding",
        "refiner",
        "git_candidate",
        "composer",
    }
    assert len({item.id for item in capabilities}) == len(capabilities)


def test_future_capability_cannot_be_release_scoped(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        """capabilities:
  - id: refiner
    status: future
    risk_level: read
    release_suite: true
    command: []
    required_dependencies: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="future capability.*release_suite"):
        load_capabilities(path)
