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


def test_output_center_has_all_composer_controls_and_single_recovery_fetch_path():
    source = _read("web/app/report/page.tsx")
    assert '"cv"' in source
    assert '"range"' in source
    assert "useSearchParams" in source
    assert all(f'"{kind}"' in source for kind in ("weekly", "monthly", "review", "cv"))
    assert "api.composeOutput(" in source
    # The only direct achievement request is for recovery guidance; formal output
    # is composed by the server's ready-only boundary.
    assert source.count("api.listAchievements(") == 1
