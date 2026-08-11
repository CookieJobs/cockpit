from __future__ import annotations

import json

from app.harness.synthetic.runner import run_synthetic_dogfooding


def test_runner_generates_ready_only_weekly_and_full_window_report_artefacts(tmp_path) -> None:
    run_synthetic_dogfooding(output_dir=tmp_path)

    weekly = [
        json.loads((tmp_path / "reports" / "product_manager" / f"week-{week}.json").read_text())
        for week in range(1, 5)
    ]
    full_window = json.loads((tmp_path / "reports" / "product_manager" / "full-window.json").read_text())

    assert all(report["synthetic"] is True for report in weekly)
    assert [report["window"]["since"] for report in weekly] == [
        "2026-07-06", "2026-07-13", "2026-07-20", "2026-07-27"
    ]
    assert full_window["window"] == {
        "since": "2026-07-06", "until": "2026-07-27", "label": "完整模拟周期"
    }
    assert "待补充留存证据" not in full_window["markdown"]
    assert all("待补充留存证据" not in report["markdown"] for report in weekly)

    designer = json.loads((tmp_path / "reports" / "independent_designer" / "full-window.json").read_text())
    assert "咨询表单增加 6 条" in designer["markdown"]
