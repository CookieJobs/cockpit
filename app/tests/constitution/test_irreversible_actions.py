"""L2 test for the explicit confirmation protocol around destructive operations."""

from pathlib import Path


def test_project_deletion_requires_explicit_confirmation_protocol() -> None:
    prompt = (Path(__file__).parents[3] / "app" / "llm" / "prompts" / "cockpit_system.md").read_text(encoding="utf-8")

    assert "delete_project" in prompt
    assert "确认删除吗" in prompt
