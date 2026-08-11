"""Current runtime contract must not be contradicted by operator-facing docs."""
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_runtime_prompt_matches_readiness_and_output_contract():
    prompt = _read("app/llm/prompts/cockpit_system.md")
    assert "只读取 ready 成就" in prompt
    assert "确认最终 CV" in prompt
    assert "needs_data" in prompt
    assert "confirm_drafts" not in prompt
    assert "PR 描述" not in prompt
    assert "思维链" not in prompt


def test_primary_docs_describe_unified_output_and_local_backup_boundary():
    for path in ("README.md", "docs/PRD.md", "docs/GOAL.md", "AGENTS.md"):
        source = _read(path)
        assert "数据与备份" in source, path
        assert "needs_data" in source, path
    assert "/report" in _read("README.md")
    assert "cockpit-career-memory" in _read("README.md")


def test_capability_catalog_includes_composer_portability_and_feedback_checks():
    capabilities = _read("docs/harness/capabilities-v1.yaml")
    assert "id: composer" in capabilities and "status: implemented" in capabilities
    assert "test_composer.py" in capabilities
    assert "test_portability.py" in capabilities
    assert "test_completion_feedback_loop.py" in capabilities
    assert "test_core_loop_cross_entry.py" in capabilities
