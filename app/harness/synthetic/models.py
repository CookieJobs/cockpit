"""Data contract for auditable synthetic work events."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SyntheticModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class Persona(SyntheticModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    role: str = Field(min_length=1, max_length=100)
    industry: str = Field(min_length=1, max_length=100)
    work_context: str = Field(min_length=1, max_length=500)


class WorkEvent(SyntheticModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    persona_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    week: int = Field(ge=1, le=4)
    completed_on: date
    project_name: str = Field(min_length=1, max_length=200)
    task_title: str = Field(min_length=1, max_length=500)
    outcome: str = Field(min_length=1, max_length=5000)
    cv: str = Field(min_length=1, max_length=5000)
    reflection: str | None = Field(default=None, max_length=5000)
    evidence: list[str] = Field(min_length=1, max_length=20)
    follow_up_answers: list[str] = Field(default_factory=list, max_length=10)
    expected_readiness: Literal["ready", "needs_data"]

    @model_validator(mode="after")
    def cv_numbers_must_be_anchored_in_evidence(self) -> "WorkEvent":
        evidence_text = " ".join([self.outcome, *self.evidence, *self.follow_up_answers])
        numeric_claims = re.findall(r"\d+(?:\.\d+)?\s*(?:%|个百分点|小时|分钟|天|个|位|条|项|张)?", self.cv)
        unsupported = [claim for claim in numeric_claims if claim and claim not in evidence_text]
        if unsupported:
            raise ValueError(f"unsupported numeric claim in cv: {', '.join(unsupported)}")
        return self


class SyntheticDataset(SyntheticModel):
    version: Literal["synthetic_dogfooding_v1"]
    personas: list[Persona] = Field(min_length=4)
    events: list[WorkEvent] = Field(min_length=16)

    @model_validator(mode="after")
    def events_must_reference_a_known_persona(self) -> "SyntheticDataset":
        persona_ids = {persona.id for persona in self.personas}
        unknown = {event.persona_id for event in self.events} - persona_ids
        if unknown:
            raise ValueError(f"events reference unknown personas: {', '.join(sorted(unknown))}")
        return self
