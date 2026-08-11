"""Human-edit feedback capture for achievement distillation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

from sqlalchemy import select

from app.core import storage
from app.core.models import _new_id


def _normalize(text: str) -> str:
    return re.sub(r"[\s,，。！？；;:：\-_/\\'\"“”‘’·…]", "", text).lower()


def classify_cv_edit(original_cv: str, final_cv: str) -> str:
    """Classify the user's final wording without interpreting it as quality."""
    original, final = _normalize(original_cv), _normalize(final_cv)
    if not final:
        return "rejected"
    if original == final:
        return "accepted"
    similarity = SequenceMatcher(None, original, final).ratio()
    if similarity >= 0.65 and abs(len(final) - len(original)) <= max(12, len(original)):
        return "minor_edit"
    if similarity >= 0.35:
        return "major_edit"
    return "rewritten"


@dataclass(frozen=True)
class DistillationFeedback:
    id: str
    trace_id: str
    original_cv: str
    final_cv: str
    edit_type: str


ConfirmationAction = Literal["confirmed", "draft", "abandoned"]


def classify_confirmation_feedback(
    original_cv: str,
    final_cv: str,
    *,
    action: ConfirmationAction,
) -> str:
    """Classify a candidate-final decision for local distillation learning."""
    if action == "draft":
        return "draft"
    if action == "abandoned" or not final_cv.strip():
        return "abandoned"
    if _normalize(original_cv) == _normalize(final_cv):
        return "direct_accept"
    similarity = SequenceMatcher(None, _normalize(original_cv), _normalize(final_cv)).ratio()
    if similarity >= 0.65 and abs(len(final_cv) - len(original_cv)) <= max(12, len(original_cv)):
        return "light_edit"
    return "rewrite"


async def record_confirmation_feedback_in_session(
    session,
    *,
    trace_id: str,
    original_cv: str,
    final_cv: str,
    action: ConfirmationAction,
) -> None:
    """Persist one confirmation decision per trace/action in its write transaction.

    Browser retries are expected on weak networks.  A confirmation is an adoption
    event, not an analytics counter, so a repeated request must not duplicate it.
    """
    existing = (await session.execute(
        select(storage.DistillationFeedbackORM).where(
            storage.DistillationFeedbackORM.trace_id == trace_id
        )
    )).scalars()
    if any(json.loads(row.diff_json).get("action") == action for row in existing):
        return
    edit_type = classify_confirmation_feedback(original_cv, final_cv, action=action)
    session.add(storage.DistillationFeedbackORM(
        id=_new_id("feedback"),
        trace_id=trace_id,
        original_cv=original_cv,
        final_cv=final_cv,
        edit_type=edit_type,
        diff_json=json.dumps(
            {"original": original_cv, "final": final_cv, "action": action},
            ensure_ascii=False,
        ),
    ))


async def record_feedback(trace_id: str, original_cv: str, final_cv: str) -> DistillationFeedback:
    feedback = DistillationFeedback(_new_id("feedback"), trace_id, original_cv, final_cv, classify_cv_edit(original_cv, final_cv))
    async with storage.get_session() as session:
        session.add(storage.DistillationFeedbackORM(
            id=feedback.id, trace_id=feedback.trace_id, original_cv=feedback.original_cv,
            final_cv=feedback.final_cv, edit_type=feedback.edit_type,
            diff_json=json.dumps({"original": original_cv, "final": final_cv}, ensure_ascii=False),
        ))
    return feedback


async def get_latest_feedback() -> DistillationFeedback | None:
    async with storage.get_session() as session:
        row = (await session.execute(select(storage.DistillationFeedbackORM).order_by(storage.DistillationFeedbackORM.created_at.desc()))).scalars().first()
        return None if row is None else DistillationFeedback(row.id, row.trace_id, row.original_cv, row.final_cv, row.edit_type)
