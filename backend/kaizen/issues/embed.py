"""Turns comments into vectors so similar meanings end up close together (FR4).

Uses the all-MiniLM-L6-v2 sentence model through fastembed, which runs it with ONNX and
needs no PyTorch. The model (about 90MB) downloads on first use into KAIZEN_EMBED_CACHE, or
fastembed's default cache folder if that is not set.
"""

from __future__ import annotations

import os
from typing import Protocol, Sequence

import numpy as np

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder(Protocol):
    name: str

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


def normalise(vectors: np.ndarray) -> np.ndarray:
    """Unit length, so Euclidean distance ranks pairs the same way cosine similarity does."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class SentenceEmbedder:
    def __init__(self, model: str | None = None) -> None:
        from fastembed import TextEmbedding  # imported here so tests never load the model

        self.name = model or os.environ.get("KAIZEN_EMBED_MODEL", DEFAULT_MODEL)
        self._model = TextEmbedding(self.name, cache_dir=os.environ.get("KAIZEN_EMBED_CACHE"))

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return normalise(np.array(list(self._model.embed(list(texts)))))
