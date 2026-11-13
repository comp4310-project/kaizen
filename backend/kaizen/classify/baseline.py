"""TF-IDF and logistic regression, the simple model the LLM has to beat (P3 section 4).

Trained on labelled comments, usually the synthetic set, whose labels come from the
generator templates. One model per label; problem categories use one yes/no model each.
"""

from __future__ import annotations

from typing import Sequence

from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency
from kaizen.classify.prompt import CommentInput


def _features(item: CommentInput) -> str:
    # The source matters (staff and patients describe the same problem differently), so it
    # goes in as a token.
    return f"__{item.source}__ {item.text}"


def _single(y: list[str]):
    """A logistic regression, or a constant guess if the training data has only one class."""
    if len(set(y)) < 2:
        return DummyClassifier(strategy="most_frequent")
    return LogisticRegression(max_iter=2000, class_weight="balanced")


class BaselineLabeller:
    name = "tfidf-logreg"
    version = "1"

    def __init__(self) -> None:
        self._models: dict = {}

    def fit(self, items: Sequence[CommentInput], labels: Sequence[Labels]) -> "BaselineLabeller":
        if len(items) != len(labels) or not items:
            raise ValueError("need the same number of comments and labels, and at least one")
        x = [_features(i) for i in items]
        for field in ("sentiment", "stage", "urgency"):
            y = [getattr(lab, field).value for lab in labels]
            self._models[field] = make_pipeline(_vectorizer(), _single(y)).fit(x, y)
        # One yes/no model per category. A category that is always or never present in the
        # training data gets a constant answer instead of a crash.
        for category in Category:
            y = [category in lab.categories for lab in labels]
            self._models[category] = make_pipeline(_vectorizer(), _single(y)).fit(x, y)
        return self

    def label(self, items: Sequence[CommentInput]) -> dict[int, Labels]:
        if not self._models:
            raise RuntimeError("call fit() first")
        x = [_features(i) for i in items]
        sentiment = self._models["sentiment"].predict(x)
        stage = self._models["stage"].predict(x)
        urgency = self._models["urgency"].predict(x)
        present = {category: self._models[category].predict(x) for category in Category}
        return {
            item.id: Labels(
                sentiment=Sentiment(sentiment[i]),
                categories=[category for category in Category if present[category][i]],
                stage=Stage(stage[i]),
                urgency=Urgency(urgency[i]),
            )
            for i, item in enumerate(items)
        }


def _vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
