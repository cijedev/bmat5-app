"""Phase 6: automated clinical escalation from PHQ-9 / GAD-7 submissions."""
from __future__ import annotations

from datetime import datetime, timedelta

from .extensions import db
from .models import ClinicalReview

# Configurable thresholds (moderately severe / severe screenings).
ESCALATION_PHQ_TOTAL = 15
ESCALATION_GAD_TOTAL = 15
ESCALATION_DEDUPE_DAYS = 7

REASON_PHQ_ITEM9 = "phq_item9"
REASON_PHQ_TOTAL = "phq9_ge_15"
REASON_GAD_TOTAL = "gad7_ge_15"


def _has_recent_open(user_id: int, reason_code: str) -> bool:
    since = datetime.utcnow() - timedelta(days=ESCALATION_DEDUPE_DAYS)
    return (
        ClinicalReview.query.filter(
            ClinicalReview.user_id == user_id,
            ClinicalReview.review_type == "escalation",
            ClinicalReview.reason_code == reason_code,
            ClinicalReview.resolved_at.is_(None),
            ClinicalReview.created_at >= since,
        ).first()
        is not None
    )


def _add_escalation(user_id: int, reason_code: str, note: str) -> bool:
    if _has_recent_open(user_id, reason_code):
        return False
    db.session.add(
        ClinicalReview(
            user_id=user_id,
            admin_user_id=None,
            note=note,
            review_type="escalation",
            reason_code=reason_code,
        )
    )
    return True


def maybe_create_escalations(
    *,
    user_id: int,
    kind: str,
    total_score: int,
    item9_score: int | None = None,
) -> list[str]:
    """Create open ClinicalReview escalations when thresholds are met.

    Returns list of reason_codes created (empty if none / all deduped).
    Caller must commit the session.
    """
    created: list[str] = []
    kind = (kind or "").upper()

    if kind == "PHQ9":
        if item9_score is not None and int(item9_score) > 0:
            note = (
                "[SYSTEM ESCALATION] PHQ-9 item 9 > 0 "
                f"(score={int(item9_score)}). Review for safety / care coordination."
            )
            if _add_escalation(user_id, REASON_PHQ_ITEM9, note):
                created.append(REASON_PHQ_ITEM9)
        if int(total_score) >= ESCALATION_PHQ_TOTAL:
            note = (
                f"[SYSTEM ESCALATION] PHQ-9 total ≥ {ESCALATION_PHQ_TOTAL} "
                f"(score={int(total_score)}). Moderately severe+ — needs clinical attention."
            )
            if _add_escalation(user_id, REASON_PHQ_TOTAL, note):
                created.append(REASON_PHQ_TOTAL)

    elif kind == "GAD7":
        if int(total_score) >= ESCALATION_GAD_TOTAL:
            note = (
                f"[SYSTEM ESCALATION] GAD-7 total ≥ {ESCALATION_GAD_TOTAL} "
                f"(score={int(total_score)}). Severe anxiety signal — needs clinical attention."
            )
            if _add_escalation(user_id, REASON_GAD_TOTAL, note):
                created.append(REASON_GAD_TOTAL)

    return created
