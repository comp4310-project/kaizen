"""Patient and staff feedback side by side (FR5).

Counts labelled comments by source, grouped by HCAT category, stage of care or unit, using
the current labels (a person's correction once there is one, FR6). `checked` says how many
of the counted labels a person has checked; the others are still the model's. A row is
marked `only` when one group has no comments in it, which is the "only one group reports
this" flag P3 asks for. Unit managers only get their own unit (NFR1).

A comment with two categories counts once in each, so category rows can add up to more
than the number of comments. Comments with no categories (praise, usually) are left out of
the category view but still count in `totals`.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.api.auth import get_session, require, unit_scope
from kaizen.db import ActivityLog, Comment, CommentLabel, LabelStatus, Role, Source, User

router = APIRouter()
readers = require(Role.QI, Role.ADMIN, Role.MANAGER)


def _only(patient: int, staff: int) -> str | None:
    if patient and not staff:
        return "patient"
    if staff and not patient:
        return "staff"
    return None


@router.get("/compare")
def compare(
    by: Literal["category", "stage", "unit"] = "category",
    unit: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(readers),
    session: Session = Depends(get_session),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from is after date_to")
    unit = unit_scope(user, unit)

    query = select(Comment.source, Comment.unit, CommentLabel.stage, CommentLabel.categories, CommentLabel.status).join(
        CommentLabel, CommentLabel.comment_id == Comment.id
    )
    if unit:
        query = query.where(Comment.unit == unit)
    if date_from:
        query = query.where(Comment.feedback_date >= date_from)
    if date_to:
        query = query.where(Comment.feedback_date <= date_to)

    counts: dict[str, Counter] = {}
    totals: Counter = Counter()
    checked = 0  # labels a person has confirmed or corrected (FR6); the rest are the model's
    for source, comment_unit, stage, categories, label_status in session.execute(query):
        totals[source] += 1
        checked += label_status is LabelStatus.CONFIRMED
        keys = {"category": categories or [], "stage": [stage], "unit": [comment_unit]}[by]
        for key in keys:
            counts.setdefault(key, Counter())[source] += 1

    rows = []
    for key, c in counts.items():
        patient, staff = c[Source.PATIENT_FAMILY], c[Source.STAFF]
        rows.append({"key": key, "patient": patient, "staff": staff, "only": _only(patient, staff)})
    rows.sort(key=lambda r: (-(r["patient"] + r["staff"]), r["key"]))

    session.add(
        ActivityLog(
            user_id=user.id,
            action="view_compare",
            detail={"by": by, "unit": unit, "rows": len(rows)},
        )
    )
    session.commit()
    return {
        "by": by,
        "unit": unit,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "totals": {"patient": totals[Source.PATIENT_FAMILY], "staff": totals[Source.STAFF]},
        "checked": checked,
        "rows": rows,
    }
