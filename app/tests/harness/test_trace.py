from __future__ import annotations

import pytest

from app.harness.trace import DistillationTrace, input_hash


def test_input_hash_is_stable_without_exposing_raw_text() -> None:
    assert input_hash("敏感 outcome") == input_hash("敏感 outcome")
    assert input_hash("敏感 outcome") != input_hash("另一条 outcome")
    assert "敏感 outcome" not in input_hash("敏感 outcome")


@pytest.mark.asyncio
async def test_trace_round_trips_through_local_store(temp_db) -> None:
    from app.harness.trace import get_latest_trace, record_trace

    trace = DistillationTrace.new(
        task_title="登录优化",
        outcome="耗时从 2 秒降到 0.5 秒",
        raw_output='{"cv":"优化登录流程"}',
        parsed_output={"cv": "优化登录流程"},
        generator_status="polished",
        guardrail_results={"length_valid": True},
        final_quality_status="ready",
        model_version="test-model",
        prompt_version="test-prompt",
        dataset_version="test-dataset",
        harness_version="test-harness",
        latency_ms=12,
    )

    await record_trace(trace)
    saved = await get_latest_trace()

    assert saved is not None
    assert saved.id == trace.id
    assert saved.input_hash == input_hash("耗时从 2 秒降到 0.5 秒")
    assert saved.generator_status == "polished"
