"""Deterministic L1 evaluator for achievement distillation harness."""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationOutput,
    HardChecks,
)

EvaluationCase = AchievementDistillationCase

CANONICAL_STRONG_ACTION_VERBS = (
    "构建",
    "设计",
    "重构",
    "推动",
    "主导",
    "优化",
    "修复",
    "落地",
    "引入",
    "沉淀",
    "实现",
    "搭建",
    "制定",
    "抽象",
    "打造",
)

_OWNERSHIP_LEVELS = {
    "协助": 1,
    "参与": 2,
    "负责": 3,
    "主导": 4,
    "独立": 4,
    "独立负责": 4,
    "独立完成": 4,
    "独自完成": 4,
    "owner": 4,
    "lead": 4,
}

_KNOWN_NON_ENTITY_TOKENS = {
    "API",
    "CLI",
    "CV",
    "DAU",
    "JSON",
    "LLM",
    "MCP",
    "OKR",
    "P0",
    "P1",
    "PRD",
    "QA",
    "SQL",
    "UI",
}

_CHINESE_NUMBER_CHARS = "零〇一二两三四五六七八九十百千万亿"
_NUMBER_UNIT_OPTIONS = [
    "位",
    "个百分点",
    "百分点",
    "万",
    "亿",
    "千",
    "百",
    "十",
    "人",
    "个",
    "条",
    "段",
    "套",
    "次",
    "轮",
    "页",
    "张",
    "项",
    "场景",
    "模块",
    "团队",
    "用户",
    "天",
    "小时",
    "分钟",
    "秒",
    "周",
    "月",
    "年",
    "倍",
]
_NUMBER_UNIT_ALTS = "|".join(_NUMBER_UNIT_OPTIONS)
_NUMBER_PATTERNS = (
    re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%"),
    re.compile(rf"\d+(?:,\d{{3}})*(?:\.\d+)?(?:{_NUMBER_UNIT_ALTS})"),
    re.compile(rf"[{_CHINESE_NUMBER_CHARS}]+(?:{_NUMBER_UNIT_ALTS})"),
    re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?"),
    re.compile(r"几(?:个|位|条|人|天|小时|分钟|秒|周|月|年|倍|次|轮|套|段|项|名)"),
)

_ENTITY_PATTERNS = (
    re.compile(r"\b[A-Z][A-Za-z0-9&+._/-]*(?:\s+[A-Z][A-Za-z0-9&+._/-]*)+\b"),
    re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})+\b"),
    re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
    re.compile(r"\b[A-Z][a-z]+[A-Z][a-z]+\b"),
    re.compile(r"\b[A-Z][a-z]+[A-Z]{2,}\b"),
    re.compile(r"(?<![A-Za-z0-9_])(?:[A-Z][a-z]+(?:[A-Z][a-z]+)+|[A-Z][a-z]+[A-Z]{2,}|[A-Z][a-z]{2,}[A-Z]{2,})(?![A-Za-z0-9_])"),
)


def _join_context(case: EvaluationCase) -> str:
    parts: list[str] = [
        case.input.task_title,
        case.input.task_description or "",
        case.input.project_name or "",
        case.input.project_goal or "",
        case.input.outcome,
        case.input.reflection or "",
    ]
    return "\n".join(part for part in parts if part)


def _normalize(text: str) -> str:
    return re.sub(r"[\s,，。！？；;:：\(\)（）\[\]【】<>\-_/\\'\"“”‘’·…]", "", text).lower()


def _unique_in_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _extract_number_tokens(text: str) -> list[str]:
    tokens: list[tuple[int, int, str]] = []
    for pattern in _NUMBER_PATTERNS:
        tokens.extend((match.start(), match.end(), match.group(0)) for match in pattern.finditer(text))
    tokens.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))

    selected: list[tuple[int, int, str]] = []
    for start, end, token in tokens:
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end, _ in selected):
            continue
        selected.append((start, end, token))

    return _unique_in_order(token for _, _, token in selected)


def _supported_number_tokens(tokens: list[str], context: str) -> list[str]:
    normalized_context = _normalize(context)
    supported: list[str] = []
    for token in tokens:
        normalized_token = _normalize(token)
        if normalized_token and normalized_token in normalized_context:
            supported.append(token)
    return supported


def _extract_entity_tokens(text: str) -> list[str]:
    tokens: list[tuple[int, int, str]] = []
    for pattern in _ENTITY_PATTERNS:
        tokens.extend((match.start(), match.end(), match.group(0)) for match in pattern.finditer(text))
    tokens.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))

    selected: list[tuple[int, int, str]] = []
    for start, end, token in tokens:
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end, _ in selected):
            continue
        selected.append((start, end, token))

    return _unique_in_order(token for _, _, token in selected)


def _is_known_entity_token(token: str) -> bool:
    return token in _KNOWN_NON_ENTITY_TOKENS


def _unsupported_entity_tokens(output: str, context: str) -> list[str]:
    normalized_context = _normalize(context)
    unsupported: list[str] = []
    for token in _extract_entity_tokens(output):
        if _is_known_entity_token(token):
            continue
        if _normalize(token) not in normalized_context:
            unsupported.append(token)
    return unsupported


def _detect_action_strength(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False

    return any(stripped.startswith(verb) for verb in CANONICAL_STRONG_ACTION_VERBS)


def _leading_ownership_level(text: str) -> int:
    stripped = text.lstrip()
    best = 0
    for verb, level in _OWNERSHIP_LEVELS.items():
        if verb in stripped:
            best = max(best, level)
    return best


def _duplicate_ratio(cv: str, outcome: str) -> float:
    return SequenceMatcher(None, _normalize(cv), _normalize(outcome)).ratio()


def _has_ownership_violation(case: EvaluationCase, output: AchievementDistillationOutput) -> bool:
    input_level = _leading_ownership_level(_join_context(case))
    output_level = _leading_ownership_level(output.cv)
    return output_level > input_level


def evaluate_l1(case: EvaluationCase, output: AchievementDistillationOutput) -> HardChecks:
    context_text = _join_context(case)
    number_tokens = _extract_number_tokens(output.cv)
    supported_numbers = _supported_number_tokens(number_tokens, context_text)
    unsupported_numbers = [token for token in number_tokens if token not in supported_numbers]

    unsupported_entities = _unsupported_entity_tokens(output.cv, context_text)
    has_strong_action = _detect_action_strength(output.cv)
    likely_duplicate_outcome = _duplicate_ratio(output.cv, case.input.outcome) >= 0.9
    ownership_violation = _has_ownership_violation(case, output)
    likely_overclaim = bool(ownership_violation or unsupported_numbers or unsupported_entities)
    generator_is_fallback = output.generator_status == "fallback"
    generator_is_parse_failed = output.generator_status == "parse_failed"

    return HardChecks(
        schema_valid=True,
        length_valid=0 < len(output.cv.strip()) <= 80,
        follow_up_count_valid=len(output.follow_up_questions) <= 3,
        has_strong_action=has_strong_action,
        has_unsupported_number=bool(unsupported_numbers),
        has_unsupported_entity=bool(unsupported_entities),
        likely_duplicate_outcome=likely_duplicate_outcome,
        likely_overclaim=likely_overclaim,
        generator_is_fallback=generator_is_fallback,
        generator_is_parse_failed=generator_is_parse_failed,
        unsupported_numbers=unsupported_numbers,
        unsupported_entities=unsupported_entities,
        ownership_violation=ownership_violation,
    )


def is_l1_pass(hard_checks: HardChecks) -> bool:
    return (
        hard_checks.schema_valid
        and hard_checks.length_valid
        and hard_checks.follow_up_count_valid
        and hard_checks.has_strong_action
        and not hard_checks.has_unsupported_number
        and not hard_checks.has_unsupported_entity
        and not hard_checks.likely_duplicate_outcome
        and not hard_checks.likely_overclaim
        and not hard_checks.generator_is_fallback
        and not hard_checks.generator_is_parse_failed
        and not hard_checks.ownership_violation
    )


__all__ = ["EvaluationCase", "evaluate_l1", "is_l1_pass"]
