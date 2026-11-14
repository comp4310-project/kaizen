"""Builds the ranked issue list from saved, labelled comments (FR4).

Only negative and neutral comments are grouped, since issues are problems to fix; praise is
left out. Comments that have no labels yet are skipped, so run the labeller first. Each run
is kept, and the dashboard shows the newest one.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.db import ActivityLog, Comment, CommentLabel, Issue, IssueComment, IssueRun
from kaizen.issues.embed import Embedder
from kaizen.issues.pipeline import find_issues
from kaizen.issues.rank import IssueComment as RankInput


def load(session: Session) -> tuple[list[int], list[str], list[RankInput]]:
    rows = session.execute(
        select(Comment, CommentLabel)
        .join(CommentLabel, CommentLabel.comment_id == Comment.id)
        .where(CommentLabel.sentiment != "positive")
        .order_by(Comment.id)
    ).all()
    ids = [c.id for c, _ in rows]
    texts = [c.text for c, _ in rows]  # de-identified
    comments = [
        RankInput(
            id=c.id,
            source=c.source.value,
            sentiment=lab.sentiment,
            urgency=lab.urgency,
            stage=lab.stage,
            categories=tuple(lab.categories),
            feedback_date=c.feedback_date,
        )
        for c, lab in rows
    ]
    return ids, texts, comments


def build_issues(
    session: Session,
    embedder: Embedder,
    namer,
    *,
    min_cluster_size: int = 8,
    seed: int = 42,
    user_id: int | None = None,
) -> IssueRun:
    ids, texts, comments = load(session)
    vectors = embedder.embed(texts) if texts else None
    found, outliers = find_issues(texts, comments, vectors, min_cluster_size, seed) if texts else ([], [])

    run = IssueRun(
        embedder=embedder.name,
        namer=namer.name,
        min_cluster_size=min_cluster_size,
        comments_used=len(texts),
        outliers=len(outliers),
        as_of=max((c.feedback_date for c in comments), default=None),
        created_by=user_id,
    )
    session.add(run)
    session.flush()

    for rank, item in enumerate(found, start=1):
        cluster, stats = item.cluster, item.stats
        name = namer.name_issue(cluster.keywords, [texts[i] for i in cluster.representatives])
        issue = Issue(
            run_id=run.id,
            rank=rank,
            name=name[:120],
            keywords=cluster.keywords,
            size=stats.size,
            negative_share=stats.negative_share,
            high_share=stats.high_share,
            patient_count=stats.patient_count,
            staff_count=stats.staff_count,
            main_stage=stats.main_stage,
            top_categories=stats.top_categories,
            recent_count=stats.recent_count,
            rising=stats.rising,
            score=stats.score,
        )
        session.add(issue)
        session.flush()
        typical = set(cluster.representatives)
        session.add_all(
            IssueComment(issue_id=issue.id, comment_id=ids[i], typical=i in typical) for i in cluster.members
        )

    session.add(
        ActivityLog(
            user_id=user_id,
            action="build_issues",
            entity_type="issue_run",
            entity_id=run.id,
            detail={"issues": len(found), "comments_used": len(texts), "outliers": len(outliers)},
        )
    )
    session.commit()
    return run
