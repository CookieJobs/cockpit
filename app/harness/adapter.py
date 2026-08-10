"""Adapters that make achievement generation runnable by the offline harness."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)


class DistillationAdapter(Protocol):
    async def generate(self, input: AchievementDistillationInput) -> AchievementDistillationOutput: ...


@runtime_checkable
class CaseAwareAdapter(Protocol):
    async def generate_case(self, case: AchievementDistillationCase) -> AchievementDistillationOutput: ...


PolishCallable = Callable[[str, str], Awaitable[tuple[str, bool, list[str]]]]


async def _call_polish_cv(task_title: str, outcome: str) -> tuple[str, bool, list[str]]:
    """Invoke the existing endpoint implementation without an HTTP round trip."""
    from app.api.llm import PolishCvRequest, polish_cv

    response = await polish_cv(PolishCvRequest(task_title=task_title, outcome=outcome))
    return response.cv, response.polished, response.follow_up_questions


class PolishCvAdapter:
    """Adapter for the existing `polish_cv` capability."""

    def __init__(self, call: PolishCallable | None = None) -> None:
        self._call = call or _call_polish_cv

    async def generate(self, input: AchievementDistillationInput) -> AchievementDistillationOutput:
        cv, polished, questions = await self._call(input.task_title, input.outcome)
        return AchievementDistillationOutput(
            cv=cv,
            follow_up_questions=questions,
            generator_status="polished" if polished else "fallback",
        )


class FakeAdapter:
    """Deterministic fixture adapter keyed by evaluation-case id."""

    def __init__(self, outputs: dict[str, AchievementDistillationOutput]) -> None:
        self._outputs = outputs
        self.calls: list[str] = []

    async def generate_case(self, case: AchievementDistillationCase) -> AchievementDistillationOutput:
        self.calls.append(case.id)
        try:
            return self._outputs[case.id]
        except KeyError as exc:
            raise KeyError(f"No fake output configured for case {case.id!r}") from exc

    async def generate(self, input: AchievementDistillationInput) -> AchievementDistillationOutput:
        if len(self._outputs) != 1:
            raise RuntimeError("FakeAdapter.generate requires exactly one configured output")
        return next(iter(self._outputs.values()))
