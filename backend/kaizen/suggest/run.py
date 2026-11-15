"""What the command line and the API share: loading the drafter, and drafting for one issue (FR7).

The documents are read from KAIZEN_CORPUS_DIR (default `documents`), and the passage vectors
are cached in KAIZEN_INDEX_PATH (default `kaizen-passages.npz`), next to where the SQLite
database goes by default.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.db import Issue, IssueComment, Suggestion
from kaizen.suggest.corpus import load_corpus, split_passages
from kaizen.suggest.draft import DraftResult, IssueBrief, SuggestionDrafter, save_suggestions
from kaizen.suggest.retrieve import Embedder, PassageIndex

DEFAULT_CORPUS_DIR = "documents"
DEFAULT_INDEX_PATH = "kaizen-passages.npz"


def brief_for(session: Session, issue: Issue) -> IssueBrief:
    comment_ids = session.scalars(
        select(IssueComment.comment_id).where(IssueComment.issue_id == issue.id).order_by(IssueComment.comment_id)
    ).all()
    return IssueBrief(
        issue_id=issue.id,
        name=issue.name,
        keywords=tuple(issue.keywords),
        main_stage=issue.main_stage,
        comment_ids=tuple(comment_ids),
    )


def load_index(corpus_dir: Path | None = None, index_path: Path | None = None, embedder: Embedder | None = None) -> PassageIndex:
    """Reads every document and loads the cached vectors, embedding again only what changed."""
    corpus_dir = Path(corpus_dir or os.environ.get("KAIZEN_CORPUS_DIR", DEFAULT_CORPUS_DIR))
    index_path = Path(index_path or os.environ.get("KAIZEN_INDEX_PATH", DEFAULT_INDEX_PATH))
    passages = [p for doc in load_corpus(corpus_dir) for p in split_passages(doc)]
    if embedder is None:
        from kaizen.issues.embed import SentenceEmbedder  # the same model issue finding uses

        embedder = SentenceEmbedder()
    return PassageIndex.load_or_build(index_path, passages, embedder)


def draft_for_issue(
    session: Session, issue: Issue, drafter: SuggestionDrafter, user_id: int | None
) -> tuple[DraftResult, list[Suggestion]]:
    brief = brief_for(session, issue)
    result = drafter.draft(brief)
    return result, save_suggestions(session, brief, result, drafter, user_id)
