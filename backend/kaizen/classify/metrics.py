"""Scores predicted labels against hand labels, with the P3 targets (Table 9).

A comment the labeller skipped counts as wrong, so skipping hard comments can't raise the
score.
"""

from __future__ import annotations

from sklearn.metrics import accuracy_score, f1_score, recall_score

from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency

TARGETS = {
    "sentiment_macro_f1": 0.75,
    "category_micro_f1": 0.70,
    "stage_accuracy": 0.65,
    "urgency_high_recall": 0.80,
}

_MISSING = "missing"


def score(gold: dict[int, Labels], predicted: dict[int, Labels]) -> dict:
    ids = sorted(gold)

    def column(source: dict[int, Labels], field: str) -> list[str]:
        return [getattr(source[i], field).value if i in source else _MISSING for i in ids]

    sentiment_true, sentiment_pred = column(gold, "sentiment"), column(predicted, "sentiment")
    stage_true, stage_pred = column(gold, "stage"), column(predicted, "stage")
    urgency_true, urgency_pred = column(gold, "urgency"), column(predicted, "urgency")

    categories = list(Category)
    cat_true = [[c in gold[i].categories for c in categories] for i in ids]
    cat_pred = [[i in predicted and c in predicted[i].categories for c in categories] for i in ids]

    sentiments = [s.value for s in Sentiment]
    stages = [s.value for s in Stage]
    high_true = [u == Urgency.HIGH.value for u in urgency_true]
    high_pred = [u == Urgency.HIGH.value for u in urgency_pred]

    result = {
        "comments": len(ids),
        "missing": sum(1 for i in ids if i not in predicted),
        "sentiment_macro_f1": f1_score(sentiment_true, sentiment_pred, labels=sentiments, average="macro", zero_division=0),
        "category_micro_f1": f1_score(cat_true, cat_pred, average="micro", zero_division=0),
        "category_macro_f1": f1_score(cat_true, cat_pred, average="macro", zero_division=0),
        "category_f1": dict(
            zip(
                [c.value for c in categories],
                (float(v) for v in f1_score(cat_true, cat_pred, average=None, zero_division=0)),
            )
        ),
        "stage_accuracy": accuracy_score(stage_true, stage_pred),
        "stage_macro_f1": f1_score(stage_true, stage_pred, labels=stages, average="macro", zero_division=0),
        "stage_unclear_rate": stage_pred.count(Stage.UNCLEAR.value) / len(ids) if ids else 0.0,
        "urgency_high_recall": recall_score(high_true, high_pred, zero_division=0) if any(high_true) else None,
        "urgency_accuracy": accuracy_score(urgency_true, urgency_pred),
    }
    result["meets_target"] = {
        name: (result[name] is not None and result[name] >= target) for name, target in TARGETS.items()
    }
    return {k: (float(v) if isinstance(v, float) else v) for k, v in result.items()}
