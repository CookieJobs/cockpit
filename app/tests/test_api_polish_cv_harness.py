"""Harness observability at the public polish_cv boundary."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.harness.trace import get_latest_trace
from app.llm.base import LLMResponse
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_polish_cv_fallback_records_non_polished_trace(client: TestClient) -> None:
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=None)):
        response = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "登录优化", "outcome": "完成登录流程"},
        )

    assert response.status_code == 200
    trace = await get_latest_trace()
    assert trace is not None
    assert trace.generator_status == "fallback"
    assert trace.final_quality_status == "needs_data"


@pytest.mark.asyncio
async def test_polish_cv_rejects_unsupported_metric_at_runtime(client: TestClient) -> None:
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv":"优化登录流程，成功率提升30%","follow_up_questions":[]}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        response = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "登录优化", "outcome": "完成登录流程"},
        )

    assert response.status_code == 200
    assert response.json()["polished"] is False
    assert response.json()["cv"] == "完成「登录优化」"
    assert response.json()["trace_id"]
    trace = await get_latest_trace()
    assert trace is not None
    assert trace.error == "runtime_guardrail_rejected"
    assert trace.guardrail_results["has_unsupported_number"] is True
