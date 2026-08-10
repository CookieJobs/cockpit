"""Human-edit feedback capture for achievement distillation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

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
