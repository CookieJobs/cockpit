from __future__ import annotations

from app.harness.synthetic.review import review_synthetic_replay
from app.harness.synthetic.runner import run_synthetic_dogfooding


def test_review_reports_coverage_and_rejects_non_ready_output_leaks(tmp_path) -> None:
    replay = run_synthetic_dogfooding(output_dir=tmp_path)
    assert (tmp_path / "review.json").exists()
    review = review_synthetic_replay(output_dir=tmp_path, replay=replay)

    assert review.synthetic is True
    assert review.metrics.completion_rate == 1.0
    assert review.metrics.ready_rate == 0.75
    assert review.metrics.weekly_coverage == 1.0
    assert review.metrics.full_window_coverage == 1.0
    assert review.p0_findings == []
    assert review.limitations
