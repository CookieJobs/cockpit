from __future__ import annotations

from app.harness.synthetic.fixtures import load_synthetic_dataset
from app.harness.synthetic.models import WorkEvent
from pydantic import ValidationError
import pytest


def test_v1_fixture_has_four_distinct_personas_and_four_weeks_of_events() -> None:
    dataset = load_synthetic_dataset()

    assert dataset.version == "synthetic_dogfooding_v1"
    assert {persona.id for persona in dataset.personas} == {
        "product_manager",
        "engineering_lead",
        "growth_operator",
        "independent_designer",
    }
    assert {persona.role for persona in dataset.personas} == {
        "B2C 产品经理",
        "工程团队负责人",
        "增长运营负责人",
        "独立设计师",
    }
    assert {event.week for event in dataset.events} == {1, 2, 3, 4}
    assert all(event.evidence for event in dataset.events)
    assert {event.expected_readiness for event in dataset.events} == {"ready", "needs_data"}


def test_work_event_rejects_cv_number_that_has_no_evidence_anchor() -> None:
    with pytest.raises(ValidationError, match="unsupported numeric claim"):
        WorkEvent(
            id="unsupported_number",
            persona_id="product_manager",
            week=1,
            completed_on="2026-07-06",
            project_name="新手引导优化",
            task_title="复盘首日数据",
            outcome="整理了首日漏斗数据。",
            cv="将激活率提升 30%。",
            evidence=["首日漏斗数据已整理"],
            expected_readiness="ready",
        )
