"""Finding the passages most relevant to an issue (FR7). A fake embedder keeps CI offline."""

from __future__ import annotations

import numpy as np
import pytest

from kaizen.suggest.corpus import Passage
from kaizen.suggest.retrieve import PassageIndex

TOPICS = ["discharge", "noise", "triage", "pharmacy"]


class FakeEmbedder:
    """One dimension per topic word, so similarity is easy to reason about."""

    name = "fake-topics"

    def __init__(self) -> None:
        self.batches: list[int] = []  # how many texts each call embedded

    def embed(self, texts):
        self.batches.append(len(texts))
        return np.array([[float(t.lower().count(word)) for word in TOPICS] for t in texts])


def passage(n: int, text: str) -> Passage:
    return Passage(id=f"doc:{n}", document_id="doc", title="Policy", heading="", text=text)


PASSAGES = [
    passage(0, "Noise at night keeps patients awake; quiet hours start at 22:00."),
    passage(1, "Discharge prescriptions go to the pharmacy the day before discharge."),
    passage(2, "Triage nurses reassess waiting patients every hour."),
    passage(3, "Discharge planning starts on admission."),
]


def test_search_returns_the_closest_passages_first() -> None:
    index = PassageIndex.build(PASSAGES, FakeEmbedder())
    hits = index.search("discharge medications delayed by pharmacy", k=2)
    assert [p.id for p, _ in hits] == ["doc:1", "doc:3"]
    assert hits[0][1] >= hits[1][1]


def test_k_larger_than_the_corpus_returns_everything() -> None:
    index = PassageIndex.build(PASSAGES, FakeEmbedder())
    assert len(index.search("noise", k=50)) == len(PASSAGES)


def test_min_score_drops_unrelated_passages() -> None:
    index = PassageIndex.build(PASSAGES, FakeEmbedder())
    assert [p.id for p, _ in index.search("noise", k=5)] == ["doc:0"] + [p.id for p in PASSAGES if p.id != "doc:0"]
    assert [p.id for p, _ in index.search("noise", k=5, min_score=0.1)] == ["doc:0"]


def test_empty_index_finds_nothing() -> None:
    assert PassageIndex.build([], FakeEmbedder()).search("noise") == []


def test_saved_index_is_reused_only_for_the_same_passages_and_model(tmp_path) -> None:
    path = tmp_path / "index.npz"
    embedder = FakeEmbedder()
    PassageIndex.build(PASSAGES, embedder).save(path)

    loaded = PassageIndex.load_or_build(path, PASSAGES, embedder)
    assert embedder.batches == [4]  # loaded from disk, nothing embedded again
    assert [p.id for p, _ in loaded.search("triage", k=1)] == ["doc:2"]

    edited = PASSAGES[:2] + [passage(2, "Triage nurses reassess waiting patients every 30 minutes.")] + PASSAGES[3:]
    PassageIndex.load_or_build(path, edited, embedder)
    assert embedder.batches == [4, 1, 4]  # the query, then a rebuild because a text changed

    other = FakeEmbedder()
    other.name = "another-model"
    PassageIndex.load_or_build(path, edited, other)
    assert other.batches == [4]


def test_wrong_number_of_vectors_is_caught() -> None:
    class Broken(FakeEmbedder):
        def embed(self, texts):
            return super().embed(texts)[:-1]

    with pytest.raises(ValueError, match="vector"):
        PassageIndex.build(PASSAGES, Broken())
