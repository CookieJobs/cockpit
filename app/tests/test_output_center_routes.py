"""Phase 2 output-center route and single-composer regressions."""
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_cv_route_redirects_to_output_center_with_all_range():
    source = _read("web/app/cv/page.tsx")
    assert 'redirect("/report?type=cv&range=all")' in source
    assert "generateCvMarkdown" not in source
    assert "listAchievements" not in source


def test_output_center_has_cv_control_and_single_achievement_fetch_path():
    source = _read("web/app/report/page.tsx")
    assert '"cv"' in source
    assert '"range"' in source
    assert "useSearchParams" in source
    assert source.count("api.listAchievements(") == 2
