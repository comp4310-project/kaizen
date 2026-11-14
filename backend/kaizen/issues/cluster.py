"""Groups comment vectors into recurring issues (FR4).

The same steps BERTopic uses: reduce the vectors to a few dimensions with UMAP, find dense
groups with HDBSCAN, then describe each group with the words that set it apart (class-based
TF-IDF). HDBSCAN leaves comments that fit no group as outliers instead of forcing them in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

# De-identification tags and filler that say nothing about the problem.
_STOP_WORDS = sorted(
    ENGLISH_STOP_WORDS
    | {"person", "date", "phone", "email", "health_card", "record_number", "card", "record", "number"}
    | {"just", "really", "told", "said", "got", "did", "didn", "don", "hospital", "patient", "patients"}
)

# Below this many comments UMAP has too few neighbours to be useful, so HDBSCAN runs on the
# full vectors instead.
UMAP_MIN_COMMENTS = 50


@dataclass
class Cluster:
    members: list[int]  # positions in the input list
    keywords: list[str] = field(default_factory=list)
    representatives: list[int] = field(default_factory=list)  # positions closest to the centre


def reduce(vectors: np.ndarray, seed: int = 42) -> np.ndarray:
    if len(vectors) < UMAP_MIN_COMMENTS:
        return vectors
    from umap import UMAP  # slow to import, so only when needed

    # A fixed seed makes UMAP single-threaded; the pinned layout keeps results the same when
    # umap-learn changes its default (NFR5).
    return UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=seed,
        n_jobs=1,
        compatibility_layout=True,
    ).fit_transform(vectors)


def find_clusters(
    texts: Sequence[str],
    vectors: np.ndarray,
    min_cluster_size: int = 8,
    seed: int = 42,
    n_keywords: int = 8,
    n_representatives: int = 10,
) -> tuple[list[Cluster], list[int]]:
    """Returns the clusters, largest first, and the positions of the outliers."""
    if len(texts) != len(vectors):
        raise ValueError("need one vector per text")
    if len(texts) < max(2, min_cluster_size):
        return [], list(range(len(texts)))

    labels = HDBSCAN(min_cluster_size=min_cluster_size, copy=True).fit_predict(reduce(vectors, seed))
    clusters = [Cluster(members=[i for i, lab in enumerate(labels) if lab == k]) for k in sorted(set(labels) - {-1})]
    clusters.sort(key=lambda c: len(c.members), reverse=True)
    outliers = [i for i, lab in enumerate(labels) if lab == -1]

    _add_keywords(clusters, texts, n_keywords)
    for cluster in clusters:
        group = vectors[cluster.members]
        centre = group.mean(axis=0)
        closest = np.argsort(-(group @ centre))[:n_representatives]
        cluster.representatives = [cluster.members[i] for i in closest]
    return clusters, outliers


def _add_keywords(clusters: list[Cluster], texts: Sequence[str], n_keywords: int) -> None:
    """Class-based TF-IDF: each cluster's comments are joined into one document."""
    if not clusters:
        return
    documents = [" ".join(texts[i] for i in c.members) for c in clusters]
    vectorizer = CountVectorizer(stop_words=_STOP_WORDS, ngram_range=(1, 2), min_df=1)
    counts = vectorizer.fit_transform(documents).toarray().astype(float)
    words = vectorizer.get_feature_names_out()
    tf = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    average_words = counts.sum() / len(clusters)
    idf = np.log(1 + average_words / np.maximum(counts.sum(axis=0), 1))
    scores = tf * idf
    for cluster, row in zip(clusters, scores):
        cluster.keywords = [str(words[j]) for j in np.argsort(-row)[:n_keywords] if row[j] > 0]
