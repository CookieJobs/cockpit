"""Phase 2 product-subtraction route and navigation regressions."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).parent.parent.parent


def test_pr_route_and_api_are_not_registered():
    client = TestClient(app)
    response = client.post("/api/llm/generate_pr", json={
        "project_name": "不应存在",
        "achievements": [{"title": "不应存在"}],
    })

    assert response.status_code == 404


def test_main_navigation_has_no_pr_or_pr_candidate_storage():
    runtime_files = [
        ROOT / "web" / "components" / "MainBoard.tsx",
        ROOT / "web" / "app" / "achievements" / "page.tsx",
        ROOT / "web" / "lib" / "api.ts",
    ]
    runtime_source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)

    assert 'href="/pr"' not in runtime_source
    assert "cockpit_pr_candidates" not in runtime_source
    assert "generatePr" not in runtime_source
