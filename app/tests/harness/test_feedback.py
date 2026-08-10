from __future__ import annotations

from app.harness.feedback import classify_cv_edit


def test_identical_cv_is_accepted() -> None:
    assert classify_cv_edit("优化登录流程", "优化登录流程") == "accepted"


def test_small_edit_is_minor() -> None:
    assert classify_cv_edit("优化登录流程", "优化登录流程，降低耗时") == "minor_edit"


def test_large_rewrite_is_rewritten() -> None:
    assert classify_cv_edit("优化登录流程", "建立支付风控体系并覆盖多个场景") == "rewritten"
