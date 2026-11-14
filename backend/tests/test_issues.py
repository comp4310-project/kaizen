"""Issue finding and ranking (FR4). A fake embedder stands in for the sentence model."""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta

import kaizen.classify  # noqa: F401  (must load before litellm, see its __init__)
import litellm
import numpy as np
from sqlalchemy import select

from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, Issue, IssueComment, Source
from kaizen.issues.build import build_issues
from kaizen.issues.cluster import Cluster, find_clusters
from kaizen.issues.embed import normalise
from kaizen.issues.evaluate import planted_recovery, rating_sheet
from kaizen.issues.name import IssueNamer, KeywordNamer
from kaizen.issues.pipeline import FoundIssue
from kaizen.issues.rank import IssueComment as RankInput
from kaizen.issues.rank import issue_stats
from tests.test_classify import FakeCompletion, raises, reply

TOPICS = {
    "pharmacy": "Discharge was delayed because pharmacy had not filled the pharmacy order",
    "noise": "Too much noise at night on the ward, the noise kept me awake",
    "triage": "Triage in ED took hours and triage nurses gave no update",
}


class FakeEmbedder:
    """Comments that share a topic word land close together; anything else lands at random."""

    name = "fake"

    def embed(self, texts):
        rng = np.random.default_rng(0)
        centres = {word: rng.normal(size=16) * 5 for word in TOPICS}
        rows = []
        for text in texts:
            word = next((w for w in TOPICS if w in text), None)
            centre = centres[word] if word else rng.normal(size=16) * 5
            rows.append(centre + rng.normal(scale=0.3, size=16))
        return normalise(np.array(rows))


def topic_texts(per_topic: int, strays: int = 0) -> tuple[list[str], list[str | None]]:
    texts, topics = [], []
    for word, sentence in TOPICS.items():
        for n in range(per_topic):
            texts.append(f"{sentence} ({n})")
            topics.append(word)
    for n in range(strays):
        texts.append(f"Unrelated remark number {n}")
        topics.append(None)
    return texts, topics


def test_small_sets_cluster_without_umap() -> None:
    texts, topics = topic_texts(10, strays=3)
    clusters, outliers = find_clusters(texts, FakeEmbedder().embed(texts), min_cluster_size=5)

    assert len(clusters) == 3
    for cluster in clusters:
        words = {topics[i] for i in cluster.members}
        assert len(words) == 1 and None not in words
        assert next(iter(words)) in " ".join(cluster.keywords)
        assert set(cluster.representatives) <= set(cluster.members)
    assert all(topics[i] is None for i in outliers)


def test_larger_sets_go_through_umap() -> None:
    texts, topics = topic_texts(25)
    clusters, _ = find_clusters(texts, FakeEmbedder().embed(texts), min_cluster_size=8)
    assert sorted({topics[i] for i in c.members}.pop() for c in clusters) == sorted(TOPICS)


def test_too_few_comments_are_all_outliers() -> None:
    clusters, outliers = find_clusters(["a", "b"], np.eye(2), min_cluster_size=8)
    assert clusters == [] and outliers == [0, 1]


def comment(n: int, *, sentiment="negative", urgency="low", source="patient_family", stage="care_on_the_ward", day=date(2026, 10, 31)):
    return RankInput(n, source, sentiment, urgency, stage, ("environment",), day)


def test_score_weights_negativity_and_urgency() -> None:
    as_of = date(2026, 10, 31)
    neutral = issue_stats([comment(i, sentiment="neutral") for i in range(10)], as_of)
    negative = issue_stats([comment(i) for i in range(10)], as_of)
    urgent = issue_stats([comment(i, urgency="high") for i in range(10)], as_of)
    assert (neutral.score, negative.score, urgent.score) == (5.0, 15.0, 30.0)

    mixed = issue_stats(
        [comment(0, source="staff", stage="admissions"), comment(1, stage="admissions"), comment(2)], as_of
    )
    assert (mixed.patient_count, mixed.staff_count, mixed.main_stage) == (2, 1, "admissions")
    assert mixed.top_categories == ["environment"]


def test_rising_compares_last_week_with_the_four_before() -> None:
    as_of = date(2026, 10, 31)
    steady = [comment(i, day=as_of - timedelta(days=i)) for i in range(35)]  # one a day
    jump = [comment(i, day=as_of - timedelta(days=30)) for i in range(2)] + [comment(10 + i, day=as_of) for i in range(4)]
    assert issue_stats(steady, as_of).rising is False
    stats = issue_stats(jump, as_of)
    assert stats.rising is True and stats.recent_count == 4


def add_labelled(app, texts: list[str], sentiment="negative", source=Source.PATIENT_FAMILY) -> list[int]:
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        ids = []
        for n, text in enumerate(texts):
            c = Comment(batch_id=batch.id, source=source, unit="4B", feedback_date=date(2026, 10, 1 + n % 28), text=text)
            session.add(c)
            session.flush()
            label = {"sentiment": sentiment, "categories": ["institutional_processes"], "stage": "discharge_and_transfers", "urgency": "medium"}
            session.add(CommentLabel(comment_id=c.id, suggested=label, labeller="fake", prompt_version="x", **label))
            ids.append(c.id)
        session.commit()
        return ids


def test_build_saves_ranked_issues_and_skips_praise(app) -> None:
    texts, _ = topic_texts(10)
    add_labelled(app, texts[:20])  # pharmacy and noise, from patients
    add_labelled(app, texts[20:], source=Source.STAFF)  # triage, from staff
    praise = add_labelled(app, ["Lovely staff, thank you"] * 10, sentiment="positive")

    with app.state.sessionmaker() as session:
        run = build_issues(session, FakeEmbedder(), KeywordNamer(), min_cluster_size=5)
        assert (run.comments_used, run.outliers) == (30, 0)
        issues = session.scalars(select(Issue).where(Issue.run_id == run.id).order_by(Issue.rank)).all()
        assert [i.rank for i in issues] == [1, 2, 3]
        assert all(i.size == 10 for i in issues)
        assert sorted((i.patient_count, i.staff_count) for i in issues) == [(0, 10), (10, 0), (10, 0)]
        members = session.scalars(select(IssueComment.comment_id)).all()
        assert len(members) == 30 and not set(praise) & set(members)
        assert sum(m.typical for m in session.scalars(select(IssueComment))) == 30  # 10 typical per issue
        assert session.scalars(select(ActivityLog).where(ActivityLog.action == "build_issues")).one().detail["issues"] == 3


def test_rating_sheet_lists_ten_comments_per_issue(app, tmp_path) -> None:
    texts, _ = topic_texts(12)
    add_labelled(app, texts)
    with app.state.sessionmaker() as session:
        build_issues(session, FakeEmbedder(), KeywordNamer(), min_cluster_size=5)
        assert rating_sheet(session, tmp_path / "sheet.csv") == 3
    rows = list(csv.reader((tmp_path / "sheet.csv").open(encoding="utf-8")))
    assert rows[0][:4] == ["rank", "issue_name", "comment_id", "comment"]
    assert len(rows) == 1 + 3 * 10


def test_planted_recovery_needs_purity_and_coverage() -> None:
    planted = ["a"] * 10 + ["b"] * 10 + [None] * 5
    found = [
        FoundIssue(Cluster(members=list(range(0, 8))), None),  # 8 of 10 "a": found
        FoundIssue(Cluster(members=[10, 20, 21, 22, 23]), None),  # mostly unplanted: not "b"
        FoundIssue(Cluster(members=[11, 12]), None),  # pure "b" but only 20% of it
    ]
    result = planted_recovery(found, planted)
    assert result == {"found": 1, "planted": 2, "rank_of": {"a": 1, "b": None}}


def test_llm_names_are_trimmed_and_failures_fall_back_to_keywords() -> None:
    keywords = ["pharmacy", "discharge", "pharmacy order"]
    long_name = json.dumps({"name": "Discharge delayed while waiting for pharmacy to fill take home orders."})
    fake = FakeCompletion(lambda _: reply(long_name))
    assert IssueNamer(completion=fake).name_issue(keywords, ["<PERSON> waited for pharmacy"]) == (
        "Discharge delayed while waiting for pharmacy to fill"
    )
    call = fake.calls[0]
    assert json.loads(call["messages"][1]["content"]) == {"keywords": keywords, "comments": ["<PERSON> waited for pharmacy"]}
    assert call["model"] == "anthropic/claude-haiku-5-5"
    assert call["response_format"]["json_schema"]["schema"]["required"] == ["name"]

    fallback = "Pharmacy, discharge"
    refused = FakeCompletion(lambda _: reply("", finish_reason="content_filter"))
    assert IssueNamer(completion=refused).name_issue(keywords, []) == fallback
    offline = FakeCompletion(raises(litellm.APIConnectionError("no route", "anthropic", "claude-haiku-5-5")))
    assert IssueNamer(completion=offline).name_issue(keywords, []) == fallback
    garbled = FakeCompletion(lambda _: reply("not json"))
    assert IssueNamer(completion=garbled).name_issue(keywords, []) == fallback
