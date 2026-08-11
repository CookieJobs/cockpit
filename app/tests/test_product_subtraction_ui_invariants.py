"""Phase 2 product-surface regressions for the intentionally smaller UI."""
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_home_keeps_only_achievements_output_center_and_settings_navigation():
    source = _read("web/components/MainBoard.tsx")
    assert 'href="/achievements"' in source
    assert 'href="/report"' in source
    assert 'href="/settings"' in source
    for retired in ('href="/cv"', 'href="/integrations"', "IntegrationNavLink"):
        assert retired not in source


def test_home_has_no_commitment_or_duplicate_completion_views():
    source = _read("web/components/MainBoard.tsx")
    for retired in ("commitments", "DoneTodaySection", "RecentAchievementsSection"):
        assert retired not in source


def test_onboarding_is_inline_empty_state_not_delayed_modal():
    source = _read("web/components/OnboardingTooltip.tsx")
    assert "setTimeout" not in source
    assert "fixed inset-0" not in source


def test_integrations_are_optional_settings_advanced_section_without_polling():
    assert 'href="/integrations"' in _read("web/app/settings/page.tsx")
    assert "refreshInterval: 30000" not in _read("web/app/integrations/page.tsx")


def test_achievements_show_evidence_health_not_quality_scores():
    source = _read("web/app/achievements/page.tsx")
    for retired in ("量化率", "强动词", "动词分布", "优秀", "achievement-stats"):
        assert retired not in source


def test_tags_are_not_exposed_by_product_models_or_frontend_dto():
    assert "tags: List[str]" not in _read("app/core/models.py")
    assert "tags: string[]" not in _read("web/lib/api.ts")
