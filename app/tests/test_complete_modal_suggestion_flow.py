"""Source-level P0 regressions for the completion suggestion flow."""
from pathlib import Path


MODAL = Path(__file__).parent.parent.parent / "web" / "components" / "CompleteTaskModal.tsx"
MAINBOARD = Path(__file__).parent.parent.parent / "web" / "components" / "MainBoard.tsx"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_auto_suggestion_keeps_questions_and_trace_from_the_same_response():
    source = _source(MODAL)
    auto_effect = source[source.index("const [autoSuggestedCv"):source.index("const acceptSuggestion")]

    assert "setFollowUpQuestions(res.follow_up_questions" in auto_effect
    assert "setDistillationTraceId(res.trace_id)" in auto_effect


def test_delayed_suggestion_cannot_replace_newer_outcome_candidate():
    source = _source(MODAL)

    assert "AbortController" in source or "suggestionRequestId" in source
    assert "signal" in source or "requestId" in source


def test_completion_preserves_structured_question_answers_and_confirms_final_cv():
    source = _source(MODAL)

    assert "follow_up_answers" in source
    assert "confirmed_cv:" in source
    assert "follow_up_questions: followUpQuestions" in source


def test_mainboard_uses_persisted_completion_status_for_its_toast_and_refresh():
    source = _source(MAINBOARD)

    assert "const achievement = await api.completeTask" in source
    assert "achievement.cv_status" in source
    assert "achievementsReady ?? 0) + 1" not in source
