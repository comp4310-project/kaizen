"""Reproduce the 100-row quality-audit sample without regenerating the data."""
import argparse
import csv
import random
from collections import Counter
from pathlib import Path

from kaizen.evaluation.generate import write_json


def sample_positions(rows, seed=4310):
    rng = random.Random(seed)
    return [i for source in ("patient", "family", "nurse", "physician")
            for i in sorted(rng.sample([i for i, row in enumerate(rows) if row["source"] == source], 25))]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", type=Path, default=Path("data/synthetic/comments.csv"))
    p.add_argument("--out", type=Path, default=Path("work/quality-review"))
    args = p.parse_args()
    rows = list(csv.DictReader(args.csv.open(encoding="utf-8", newline="")))
    positions = sample_positions(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "sample-100.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row_id", "source", "text", "reviewer", "notes"])
        for i in positions:
            writer.writerow([i + 1, rows[i]["source"], rows[i]["text"], "", ""])
    texts = [rows[i]["text"] for i in positions]
    write_json(args.out / "sample-statistics.json", {
        "seed": 4310, "sample": len(positions), "source": dict(Counter(rows[i]["source"] for i in positions)),
        "unique_texts": len(set(texts)), "up_to_15_words": sum(len(t.split()) <= 15 for t in texts),
        "five_word_openings": Counter(" ".join(t.lower().split()[:5]) for t in texts).most_common(10),
        "review_status": "blank reviewer sheet; automated statistics are not a realism rating",
    })


if __name__ == "__main__":
    main()
