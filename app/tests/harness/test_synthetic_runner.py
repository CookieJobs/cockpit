from __future__ import annotations

import json

from app.harness.synthetic.runner import run_synthetic_dogfooding


def test_runner_replays_each_persona_through_isolated_api_backed_database(tmp_path) -> None:
    result = run_synthetic_dogfooding(output_dir=tmp_path)

    assert {run.persona_id for run in result.personas} == {
        "product_manager",
        "engineering_lead",
        "growth_operator",
        "independent_designer",
    }
    assert all(len(run.achievements) == 4 for run in result.personas)
    assert all(run.database_isolated for run in result.personas)

    product_manager = next(run for run in result.personas if run.persona_id == "product_manager")
    assert [achievement["date"] for achievement in product_manager.achievements] == [
        "2026-07-27",
        "2026-07-20",
        "2026-07-13",
        "2026-07-06",
    ]
    assert product_manager.achievements[0]["cv_status"] == "needs_data"
    assert all(
        achievement["title"] in {"梳理激活漏斗", "协调引导页方案", "上线引导页灰度", "补充留存对比"}
        for achievement in product_manager.achievements
    )

    replay = json.loads((tmp_path / "replay.json").read_text(encoding="utf-8"))
    assert replay["synthetic"] is True
    assert replay["database_location"] == "temporary and discarded"
