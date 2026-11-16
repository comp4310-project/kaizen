"""Aggregate-only evaluation of the existing pinned FFT public-data extract.

FFT supplies five-point sentiment labels, not HCAT stage/category/urgency labels.
Raw text is passed only to de-identification, then discarded.
"""
import csv
from collections import Counter

from sklearn.metrics import f1_score

from kaizen.classify.prompt import CommentInput
from kaizen.deid import deidentify
from kaizen.evaluation.generate import digest
from kaizen.evaluation.report import check, unavailable

SENTIMENT = {"1": "positive", "2": "positive", "3": "neutral", "4": "negative", "5": "negative"}


def evaluate_public(path, labeller, batch_size=50):
    items, gold, skipped = [], {}, 0
    with path.open(encoding="utf-8", newline="") as f:
        for n, row in enumerate(csv.DictReader(f), 1):
            label = row["fft_sentiment"].strip()
            if not label:
                skipped += 1
                continue
            if label not in SENTIMENT:
                raise ValueError("unexpected FFT sentiment label")
            cleaned = deidentify(row["text"]).text
            items.append(CommentInput(id=n, text=cleaned, source="patient_family", unit="ED"))
            gold[n] = SENTIMENT[label]
    if not items:
        return unavailable("no public comments with sentiment labels")
    predicted = {}
    for start in range(0, len(items), batch_size):
        predicted.update(labeller.label(items[start:start + batch_size]))
    result = f1_score(list(gold.values()),
                      [predicted[i].sentiment.value if i in predicted else "missing" for i in gold],
                      labels=["positive", "neutral", "negative"], average="macro", zero_division=0)
    return {
        "source": "pxtextmining pinned extract; NHS NEAS See and Convey; ambulance feedback, not inpatient ward feedback",
        "extract_sha256": digest(path), "mapping": SENTIMENT, "labeller": labeller.name,
        "comments_scored": len(gold), "unlabelled_excluded": skipped,
        "gold_distribution": dict(Counter(gold.values())),
        "missing_predictions": sum(i not in predicted for i in gold),
        "sentiment_macro_f1": check(float(result), .75),
        "scope": "external published sentiment labels; diagnostic domain transfer, not Kaizen's 300-comment HCAT validation",
        "hcat_category_stage_urgency": unavailable("FFT extract has no labels for these dimensions"),
        "privacy": "no public text, identifiers, or per-comment predictions written to report",
    }
