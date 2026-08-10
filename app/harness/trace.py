"""Local, append-only observability records for distillation calls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core import storage
from app.core.models import _new_id


def input_hash(outcome: str) -> str:
    return hashlib.sha256(outcome.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DistillationTrace:
    id: str
    created_at: datetime
    task_id: str | None
    task_title: str
    outcome: str
    input_hash: str
    raw_output: str
    parsed_output: dict[str, Any]
    generator_status: str
    guardrail_results: dict[str, Any]
    final_quality_status: str
    model_version: str
    prompt_version: str
    dataset_version: str
    harness_version: str
    latency_ms: int
    error: str | None = None

    @classmethod
    def new(
        cls,
        *,
        task_title: str,
        outcome: str,
        raw_output: str,
        parsed_output: dict[str, Any],
        generator_status: str,
        guardrail_results: dict[str, Any],
        final_quality_status: str,
        model_version: str,
        prompt_version: str,
        dataset_version: str,
        harness_version: str,
        latency_ms: int,
        task_id: str | None = None,
        error: str | None = None,
    ) -> "DistillationTrace":
        return cls(
            id=_new_id("trace"),
            created_at=datetime.now(),
            task_id=task_id,
            task_title=task_title,
            outcome=outcome,
            input_hash=input_hash(outcome),
            raw_output=raw_output,
            parsed_output=parsed_output,
            generator_status=generator_status,
            guardrail_results=guardrail_results,
            final_quality_status=final_quality_status,
            model_version=model_version,
            prompt_version=prompt_version,
            dataset_version=dataset_version,
            harness_version=harness_version,
            latency_ms=latency_ms,
            error=error,
        )


async def record_trace(trace: DistillationTrace) -> None:
    async with storage.get_session() as session:
        session.add(
            storage.DistillationTraceORM(
                id=trace.id,
                created_at=trace.created_at,
                task_id=trace.task_id,
                task_title=trace.task_title,
                input_hash=trace.input_hash,
                input_json=json.dumps({"outcome": trace.outcome}, ensure_ascii=False),
                raw_output=trace.raw_output,
                parsed_output_json=json.dumps(trace.parsed_output, ensure_ascii=False),
                generator_status=trace.generator_status,
                guardrail_results_json=json.dumps(trace.guardrail_results, ensure_ascii=False),
                final_quality_status=trace.final_quality_status,
                model_version=trace.model_version,
                prompt_version=trace.prompt_version,
                dataset_version=trace.dataset_version,
                harness_version=trace.harness_version,
                latency_ms=trace.latency_ms,
                error=trace.error,
            )
        )


async def get_latest_trace() -> DistillationTrace | None:
    from sqlalchemy import select

    async with storage.get_session() as session:
        row = (
            await session.execute(
                select(storage.DistillationTraceORM).order_by(storage.DistillationTraceORM.created_at.desc())
            )
        ).scalars().first()
        if row is None:
            return None
        input_payload = json.loads(row.input_json)
        return DistillationTrace(
            id=row.id,
            created_at=row.created_at,
            task_id=row.task_id,
            task_title=row.task_title,
            outcome=input_payload.get("outcome", ""),
            input_hash=row.input_hash,
            raw_output=row.raw_output,
            parsed_output=json.loads(row.parsed_output_json),
            generator_status=row.generator_status,
            guardrail_results=json.loads(row.guardrail_results_json),
            final_quality_status=row.final_quality_status,
            model_version=row.model_version,
            prompt_version=row.prompt_version,
            dataset_version=row.dataset_version,
            harness_version=row.harness_version,
            latency_ms=row.latency_ms,
            error=row.error,
        )
