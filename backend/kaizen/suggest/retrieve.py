"""Finds the passages most relevant to an issue (FR7, the retrieval half of P3's "Suggest (RAG)").

Every passage is embedded once, and a search compares the query with all of them by cosine
similarity. P3 planned Chroma for this; `docs/decisions.md` says why we don't use it. With a
few thousand passages an exact search over all of them takes milliseconds.

The vectors are saved to disk with a fingerprint of the passage texts and the model name, so
they are only recomputed when a document or the model changes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np

from kaizen.suggest.corpus import Passage


class Embedder(Protocol):
    """Same shape as the issue embedder in `kaizen.issues.embed`, so one model serves both."""

    name: str

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


def _unit(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def _fingerprint(passages: Sequence[Passage], model: str) -> str:
    digest = hashlib.sha256(model.encode())
    for p in passages:
        digest.update(f"\0{p.id}\0{p.search_text}".encode())
    return digest.hexdigest()


@dataclass
class PassageIndex:
    passages: list[Passage]
    vectors: np.ndarray  # one unit-length row per passage
    embedder: Embedder

    @classmethod
    def build(cls, passages: Sequence[Passage], embedder: Embedder) -> "PassageIndex":
        passages = list(passages)
        if not passages:
            return cls([], np.zeros((0, 0)), embedder)
        vectors = np.asarray(embedder.embed([p.search_text for p in passages]), dtype=np.float32)
        if len(vectors) != len(passages):
            raise ValueError(f"embedder returned {len(vectors)} vectors for {len(passages)} passages")
        return cls(passages, _unit(vectors), embedder)

    @classmethod
    def load_or_build(cls, path: Path, passages: Sequence[Passage], embedder: Embedder) -> "PassageIndex":
        passages = list(passages)
        fingerprint = _fingerprint(passages, embedder.name)
        try:
            with np.load(path) as saved:
                if str(saved["fingerprint"]) == fingerprint:
                    return cls(passages, saved["vectors"], embedder)
        except (OSError, KeyError, ValueError):
            pass  # missing or unreadable: build it again
        index = cls.build(passages, embedder)
        index.save(path)
        return index

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            np.savez(f, vectors=self.vectors, fingerprint=np.array(_fingerprint(self.passages, self.embedder.name)))

    def search(self, query: str, k: int = 5, min_score: float | None = None) -> list[tuple[Passage, float]]:
        """The k passages most similar to the query, best first. Ties keep corpus order."""
        if not self.passages:
            return []
        query_vector = _unit(np.asarray(self.embedder.embed([query]), dtype=np.float32))[0]
        scores = self.vectors @ query_vector
        best = np.argsort(-scores, kind="stable")[:k]
        return [
            (self.passages[i], float(scores[i]))
            for i in best
            if min_score is None or scores[i] >= min_score
        ]
