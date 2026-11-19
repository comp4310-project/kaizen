"""Trains the TF-IDF baseline on the synthetic training split (FR3).

`data/synthetic/comments.csv` and `truth.jsonl` hold the same rows in the same order; the
truth file marks each row `train` or `test`. The training texts go through the same CSV
checks and de-identification as an upload, so the model sees text shaped like the saved
comments it will label. This is what `backend/scripts/demo_data.py` trains on, and what
"Process new feedback" in the app uses when no LLM is set.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from kaizen.classify.baseline import BaselineLabeller
from kaizen.classify.labels import Labels
from kaizen.classify.prompt import CommentInput
from kaizen.deid import deidentify
from kaizen.ingest.csv_import import parse_csv

SYNTHETIC_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic"

_cache: dict[Path, BaselineLabeller] = {}
_cache_lock = threading.Lock()


def training_split(data_dir: Path = SYNTHETIC_DIR) -> tuple[list[CommentInput], list[Labels]]:
    rows, errors = parse_csv((data_dir / "comments.csv").read_bytes())
    truth = [json.loads(line) for line in (data_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if errors or len(truth) != len(rows):
        raise ValueError(f"{data_dir}: {len(rows)} usable rows and {len(errors)} rejected, but {len(truth)} truth rows")
    train = [i for i, t in enumerate(truth) if t["split"] == "train"]
    items = [CommentInput(id=n, text=deidentify(rows[i].text).text, source=rows[i].source.value, unit=rows[i].unit)
             for n, i in enumerate(train)]
    return items, [Labels.model_validate(truth[i]) for i in train]


def synthetic_baseline(data_dir: Path = SYNTHETIC_DIR) -> BaselineLabeller:
    """The baseline trained on the training split. Trained once per process, then reused."""
    with _cache_lock:
        if data_dir not in _cache:
            items, labels = training_split(data_dir)
            _cache[data_dir] = BaselineLabeller().fit(items, labels)
        return _cache[data_dir]
