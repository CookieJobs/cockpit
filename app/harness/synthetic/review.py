"""Deterministic review for synthetic dogfooding artefacts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.harness.synthetic.fixtures import load_synthetic_dataset
from app.harness.synthetic.runner import SyntheticReplay


@dataclass(frozen=True)
class SyntheticMetrics:
    completion_rate: float
    ready_rate: float
    weekly_coverage: float
    full_window_coverage: float
    recovery_rate: float


@dataclass(frozen=True)
class SyntheticReview:
    synthetic: bool
    metrics: SyntheticMetrics
    p0_findings: list[str] = field(default_factory=list)
    p1_findings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


def _read_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def review_synthetic_replay(*, output_dir: Path, replay: SyntheticReplay) -> SyntheticReview:
    """Validate coverage and report integrity without relying on an LLM judge."""
    dataset = load_synthetic_dataset()
    expected_event_ids = {event.id for event in dataset.events}
    expected_by_persona = {
        persona.id: [event for event in dataset.events if event.persona_id == persona.id]
        for persona in dataset.personas
    }
    achievements = [achievement for persona in replay.personas for achievement in persona.achievements]
    completed = len(achievements)
    ready = [achievement for achievement in achievements if achievement["cv_status"] == "ready"]
    p0: list[str] = []
    p1: list[str] = []
    actual_report_count = 0

    for persona in replay.personas:
        known_achievements = {achievement["id"]: achievement for achievement in persona.achievements}
        expected_events = expected_by_persona[persona.persona_id]
        non_ready_claims = [
            event.cv for event in expected_events if event.expected_readiness != "ready"
        ]
        for name in [*(f"week-{week}.json" for week in range(1, 5)), "full-window.json"]:
            report_path = output_dir / "reports" / persona.persona_id / name
            if not report_path.exists():
                p1.append(f"missing_report:{persona.persona_id}:{name}")
                continue
            actual_report_count += 1
            report = _read_report(report_path)
            for achievement_id in report.get("usedAchievementIds", []):
                achievement = known_achievements.get(achievement_id)
                if achievement is None:
                    p0.append(f"unsupported_output_id:{persona.persona_id}:{achievement_id}")
                elif achievement["cv_status"] != "ready":
                    p0.append(f"non_ready_output_leak:{persona.persona_id}:{achievement_id}")
            for claim in non_ready_claims:
                if claim and claim in report.get("markdown", ""):
                    p0.append(f"non_ready_markdown_leak:{persona.persona_id}:{name}")

    if completed != len(expected_event_ids):
        p1.append(f"completion_mismatch:expected={len(expected_event_ids)}:actual={completed}")
    expected_reports = len(dataset.personas) * 5
    recovered = sum(
        1
        for event in dataset.events
        if event.expected_readiness == "needs_data"
        and any(
            achievement["title"] == event.task_title and achievement["cv_status"] == "ready"
            for persona in replay.personas
            for achievement in persona.achievements
        )
    )
    needs_data_total = sum(event.expected_readiness == "needs_data" for event in dataset.events)
    review = SyntheticReview(
        synthetic=True,
        metrics=SyntheticMetrics(
            completion_rate=completed / len(expected_event_ids),
            ready_rate=len(ready) / completed if completed else 0.0,
            weekly_coverage=(actual_report_count - len(dataset.personas)) / (len(dataset.personas) * 4),
            full_window_coverage=(actual_report_count - len(dataset.personas) * 4) / len(dataset.personas),
            recovery_rate=recovered / needs_data_total if needs_data_total else 1.0,
        ),
        p0_findings=sorted(set(p0)),
        p1_findings=sorted(set(p1)),
        limitations=[
            "Synthetic data validates workflow and evidence boundaries, not real user adoption or product-market fit.",
            "The v1 fixture does not yet simulate a completed follow-up recovery cycle.",
        ],
    )
    (output_dir / "review.json").write_text(
        json.dumps(asdict(review), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "weekly-review.md").write_text(
        "# Synthetic Dogfooding Review\n\n"
        f"- 完成率：{review.metrics.completion_rate:.0%}\n"
        f"- Ready 率：{review.metrics.ready_rate:.0%}\n"
        f"- 周覆盖率：{review.metrics.weekly_coverage:.0%}\n"
        f"- 完整周期覆盖率：{review.metrics.full_window_coverage:.0%}\n"
        f"- P0：{len(review.p0_findings)}\n\n"
        "此结果为合成模拟，不代表真实用户采用或产品市场验证。\n",
        encoding="utf-8",
    )
    return review
