"""Generate fictional hospital feedback and separate evaluation metadata."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from kaizen.evaluation.scenarios import BACKGROUND, BACKGROUND_DETAILS, DETAILS, ISSUES, PATIENT, STAFF
from kaizen.units import UNITS

SEED = 4310
START = date(2026, 9, 21)
VERSION = "2"
TRANSPORT_WEEKS = [8, 12, 18, 28, 42, 72]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(base, details, rng, family=False):
    # Some short comments; others give an extra observation or several details.
    n = rng.choices([0, 1, 2], [25, 50, 25])[0]
    parts = [base] + rng.sample(details, n)
    if family:
        relation = rng.choice(["mum", "dad", "partner", "sister", "brother"])
        parts[0] = parts[0].replace("my bed", f"my {relation}'s bed")
        parts[0] = parts[0].replace("I was", f"My {relation} was").replace("I had", f"My {relation} had")
        if parts[0] == base and rng.random() < .45:
            parts.append(f"I was there with my {relation}.")
    text = " ".join(parts)
    # Restrained variation; most rows keep conventional grammar.
    style = rng.randrange(10)
    if style == 0:
        text = text[0].lower() + text[1:]
    elif style == 1:
        text = text.rstrip(".")
    elif style == 2:
        text = text.replace("waiting", "waitng").replace("because", "becuase")
    elif style == 3:
        text = text.replace("minutes", "mins").replace("information", "info")
    elif style == 4:
        text = text.replace("did not", "didn't").replace("was not", "wasn't")
    return text


def generate(seed=SEED, apply_revision=True):
    rng = random.Random(seed)
    rows, truth, seen = [], [], set()
    transport_days = [w for w, count in enumerate(TRANSPORT_WEEKS) for _ in range(count)]
    rng.shuffle(transport_days)

    def add(base, details, source, issue, stage, categories, sentiment, scenario, split, week=None):
        for _ in range(5000):
            text = render(base, details, rng, source == "family")
            if text not in seen:
                break
        else:
            raise ValueError("scenario bank exhausted")
        seen.add(text)
        week = rng.randrange(6) if week is None else week
        day = START + timedelta(days=week * 7 + rng.randrange(7))
        unit = "ED" if issue == "ed_wait" else rng.choice([u for u in UNITS if u != "ED"])
        if issue is None:
            unit = "ED" if stage == "admissions" else rng.choice(list(UNITS))
        rows.append(dict(text=text, source=source, unit=unit, date=day.isoformat()))
        truth.append(dict(planted=issue, source_group="staff" if source in ("nurse", "physician") else "patient_family",
                          trend="increasing" if issue == "transport" else "background" if issue is None else "stable",
                          week=week + 1, scenario=scenario, split=split, annotation_origin="synthetic_intent",
                          sentiment=sentiment, categories=categories, stage=stage,
                          urgency="high" if "safety" in categories else "low" if sentiment != "negative" else "medium"))

    for issue, patients, staff, stage, cats in ISSUES:
        for group, count, bank in (("patient_family", patients, PATIENT), ("staff", staff, STAFF)):
            if not count:
                continue
            seeds = bank[issue].strip().splitlines()
            for n in range(count):
                i = n % len(seeds)
                source = rng.choice(["patient", "patient", "family"]) if group == "patient_family" else rng.choice(["nurse", "nurse", "physician"])
                add(seeds[i], DETAILS[issue], source, issue, stage, cats, "negative",
                    f"{issue}/{group}/{i}", "train" if i < 7 else "test",
                    transport_days.pop() if issue == "transport" else None)

    for group, count, indices in [
        ("patient_family", 550, list(range(22)) + [38, 39]),
        ("staff", 250, list(range(22, 38))),
    ]:
        for n in range(count):
            i = indices[n % len(indices)]
            sentiment, stage, category, base = BACKGROUND[i].split("|", 3)
            source = rng.choice(["patient", "family"]) if group == "patient_family" else rng.choice(["nurse", "physician"])
            add(base, BACKGROUND_DETAILS[sentiment], source, None, stage,
                [] if category == "-" else [category], sentiment, f"background/{i}",
                "test" if i % 3 == 0 else "train")
    paired = list(zip(rows, truth))
    rng.shuffle(paired)
    rows, truth = map(list, zip(*paired))
    for n, item in enumerate(truth, 1):
        item["row_id"] = n
    from kaizen.evaluation.revise import revise
    return (revise(rows, truth, seed) if apply_revision else rows), truth


def audit(rows, truth):
    texts = [r["text"] for r in rows]
    openings = Counter(" ".join(t.lower().split()[:5]) for t in texts)
    words = sorted(len(t.split()) for t in texts)
    return {
        "rows": len(rows), "unique_texts": len(set(texts)),
        "source": dict(Counter(r["source"] for r in rows)),
        "source_group": dict(Counter(t["source_group"] for t in truth)),
        "units": dict(Counter(r["unit"] for r in rows)),
        "sentiment_intent": dict(Counter(t["sentiment"] for t in truth)),
        "split": dict(Counter(t["split"] for t in truth)),
        "issues": dict(Counter(t["planted"] or "background" for t in truth)),
        "transport_weekly": dict(sorted(Counter(t["week"] for t in truth if t["planted"] == "transport").items())),
        "date_min": min(r["date"] for r in rows), "date_max": max(r["date"] for r in rows),
        "words_min_median_max": [words[0], words[len(words)//2], words[-1]],
        "short_rows_up_to_15_words": sum(len(t.split()) <= 15 for t in texts),
        "top_five_word_openings": openings.most_common(15),
        "narrative_seeds": len({t["scenario"] for t in truth}),
        "realism_limit": "AI-authored scenario combinations; unique text does not establish human realism. Repeated narrative seeds remain. Human review required.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=Path("data/synthetic"))
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows, truth = generate(args.seed)
    path = args.out / "comments.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "source", "unit", "date"])
        writer.writeheader()
        writer.writerows(rows)
    (args.out / "truth.jsonl").write_text("".join(json.dumps(t, sort_keys=True) + "\n" for t in truth), encoding="utf-8")
    write_json(args.out / "manifest.json", {
        "synthetic": True, "generator_version": VERSION, "seed": args.seed,
        "start": START.isoformat(), "weeks": 6, "transport_weekly": TRANSPORT_WEEKS,
        "csv_sha256": digest(path), "truth_sha256": digest(args.out / "truth.jsonl"),
        "join": "row_id is the one-based data row, never an assumed database id",
        "provenance": "AI-authored fictional scenario bank and seeded local composition. No real stories.",
        "wording_revision": {
            "from_version": "1",
            "changed_rows": sum(a != b for a, b in zip(generate(args.seed, apply_revision=False)[0], rows)),
            "metadata_unchanged": True,
            "reason": "100-row AI review: family perspective, mismatched follow-on details and unfamiliar abbreviation",
        },
        "audit": audit(rows, truth),
    })
    print(json.dumps(audit(rows, truth), indent=2))


if __name__ == "__main__":
    main()
