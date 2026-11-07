"""De-identifies checked rows and saves them, in that order (FR1, FR2, NFR1).

De-identification runs here, inside the request, so original text is never queued or
written anywhere. Later processing steps read the saved comments.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from kaizen.db import ActivityLog, Channel, Comment, ImportBatch
from kaizen.deid import deidentify
from kaizen.ingest.csv_import import FeedbackRow


def save_feedback(
    session: Session,
    rows: list[FeedbackRow],
    channel: Channel,
    user_id: int | None,
    rows_rejected: int = 0,
) -> ImportBatch:
    batch = ImportBatch(channel=channel, uploaded_by=user_id, rows_saved=len(rows), rows_rejected=rows_rejected)
    session.add(batch)
    session.flush()

    removed: dict[str, int] = {}
    for row in rows:
        result = deidentify(row.text)
        for tag, n in result.counts.items():
            removed[tag] = removed.get(tag, 0) + n
        session.add(
            Comment(
                batch_id=batch.id,
                source=row.source,
                unit=row.unit,
                feedback_date=row.feedback_date,
                text=result.text,
                deid_counts=result.counts,
            )
        )

    session.add(
        ActivityLog(
            user_id=user_id,
            action="import_csv" if channel is Channel.CSV else "submit_form",
            entity_type="import_batch",
            entity_id=batch.id,
            detail={"saved": len(rows), "rejected": rows_rejected, "removed": removed},
        )
    )
    session.commit()
    return batch
