from __future__ import annotations

from app.harness.l1 import evaluate_l1, is_l1_pass
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)


def make_case(*, outcome: str, title: str = "测试任务", description: str | None = None) -> AchievementDistillationCase:
    return AchievementDistillationCase(
        id="case_1",
        category="boundary",
        input=AchievementDistillationInput(
            task_title=title,
            task_description=description,
            project_name="测试项目",
            project_goal="测试目标",
            outcome=outcome,
            reflection=None,
            language="zh",
        ),
        expected={},
        forbidden=[],
        severity="p1",
    )


def make_output(
    *,
    cv: str,
    follow_up_questions: list[str] | None = None,
    generator_status: str = "polished",
) -> AchievementDistillationOutput:
    return AchievementDistillationOutput(
        cv=cv,
        follow_up_questions=follow_up_questions or [],
        generator_status=generator_status,  # type: ignore[arg-type]
    )


def test_unsupported_number_fails() -> None:
    case = make_case(outcome="优化登录流程")
    output = make_output(cv="优化登录流程，成功率提升 30%")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_number is True
    assert checks.unsupported_numbers == ["30%"]
    assert is_l1_pass(checks) is False


def test_participation_must_not_be_upgraded_to_leadership() -> None:
    case = make_case(outcome="我参与了推荐系统优化")
    output = make_output(cv="主导推荐系统优化")

    checks = evaluate_l1(case, output)

    assert checks.likely_overclaim is True
    assert checks.ownership_violation is True
    assert is_l1_pass(checks) is False


def test_valid_number_and_length_pass() -> None:
    case = make_case(outcome="耗时从 2 秒降到 0.5 秒")
    output = make_output(cv="优化登录流程，耗时从 2 秒降到 0.5 秒")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_number is False
    assert checks.length_valid is True
    assert checks.follow_up_count_valid is True
    assert is_l1_pass(checks) is True


def test_empty_and_exact_80_char_cv_length_boundaries() -> None:
    case = make_case(outcome="优化登录流程")

    empty_checks = evaluate_l1(
        case,
        AchievementDistillationOutput.model_construct(
            cv="",
            follow_up_questions=[],
            generator_status="polished",
        ),
    )
    exact_80_cv = "构建" + ("a" * 78)
    exact_80_checks = evaluate_l1(case, make_output(cv=exact_80_cv))

    assert empty_checks.length_valid is False
    assert exact_80_checks.length_valid is True


def test_fallback_and_parse_failed_status_are_blocked() -> None:
    case = make_case(outcome="完成成就整理")

    fallback_checks = evaluate_l1(
        case,
        make_output(cv='完成「完成成就整理」', generator_status="fallback"),
    )
    parse_failed_checks = evaluate_l1(
        case,
        make_output(cv='完成「完成成就整理」', generator_status="parse_failed"),
    )

    assert fallback_checks.generator_is_fallback is True
    assert fallback_checks.generator_is_parse_failed is False
    assert is_l1_pass(fallback_checks) is False

    assert parse_failed_checks.generator_is_fallback is False
    assert parse_failed_checks.generator_is_parse_failed is True
    assert is_l1_pass(parse_failed_checks) is False


def test_follow_up_count_above_three_fails() -> None:
    case = make_case(outcome="优化登录流程")
    output = AchievementDistillationOutput.model_construct(
        cv="优化登录流程，成功率提升 30%",
        follow_up_questions=["q1", "q2", "q3", "q4"],
        generator_status="polished",
    )

    checks = evaluate_l1(case, output)

    assert checks.follow_up_count_valid is False
    assert is_l1_pass(checks) is False


def test_unsupported_entity_is_reported() -> None:
    case = make_case(outcome="项目复盘整理完成")
    output = make_output(cv="与 Alpha Corp 完成合作复盘")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_entity is True
    assert checks.unsupported_entities == ["Alpha Corp"]
    assert is_l1_pass(checks) is False


def test_single_token_entities_are_reported_when_missing_from_context() -> None:
    case = make_case(outcome="项目复盘整理完成")
    output = make_output(cv="与 OpenAI 和 GitHub 合作复盘")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_entity is True
    assert checks.unsupported_entities == ["OpenAI", "GitHub"]


def test_chinese_adjacent_single_token_entity_is_reported() -> None:
    case = make_case(outcome="优化登录流程")
    output = make_output(cv="优化登录流程并服务OpenAI")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_entity is True
    assert checks.unsupported_entities == ["OpenAI"]
    assert is_l1_pass(checks) is False


def test_present_entity_is_not_falsely_flagged() -> None:
    case = make_case(outcome="接入OpenAI接口", description="本次需要接入OpenAI")
    output = make_output(cv="优化登录流程并服务OpenAI")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_entity is False
    assert checks.unsupported_entities == []


def test_number_tokens_are_reported_with_exact_full_token() -> None:
    case = make_case(outcome="完成培训")
    output = make_output(cv="主导培训 30 一百人 十二人 3位 0.5秒 99.99%")

    checks = evaluate_l1(case, output)

    assert checks.has_unsupported_number is True
    assert checks.unsupported_numbers == ["30", "一百人", "十二人", "3位", "0.5秒", "99.99%"]


def test_duplicate_cv_is_flagged() -> None:
    case = make_case(outcome="优化登录流程")
    output = make_output(cv="优化登录流程")

    checks = evaluate_l1(case, output)

    assert checks.likely_duplicate_outcome is True
    assert is_l1_pass(checks) is False


def test_weak_leading_verb_is_not_counted_as_strong() -> None:
    case = make_case(outcome="参与登录优化")
    output = make_output(cv="负责登录优化")

    checks = evaluate_l1(case, output)

    assert checks.has_strong_action is False


def test_non_leading_strong_verb_does_not_count() -> None:
    case = make_case(outcome="提升登录体验")
    output = make_output(cv="先评审后主导登录优化")

    checks = evaluate_l1(case, output)

    assert checks.has_strong_action is False


def test_vocab_drift_verb_does_not_count_as_strong() -> None:
    case = make_case(outcome="提升登录体验")
    output = make_output(cv="提升登录转化率")

    checks = evaluate_l1(case, output)

    assert checks.has_strong_action is False


def test_load_cases_boundary_participation_matches_modelled_behavior() -> None:
    from app.harness.datasets import load_cases

    case = next(item for item in load_cases() if item.id == "boundary_participation")
    checks = evaluate_l1(case, make_output(cv="主导首页改版"))

    assert checks.ownership_violation is True
    assert checks.likely_overclaim is True
