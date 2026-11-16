"""Reruns the whole evaluation with one command and writes the results (NFR5).

    python -m kaizen.evaluate OUT_DIR [--llm MODEL]

Needs no API key. It runs, in order:

1. De-identification on tests/data/deid_test_set.jsonl (P3 Table 9).
2. The TF-IDF baseline labeller, trained on the synthetic training split and scored on the
   300 held-out synthetic comments with the targets in kaizen.classify.metrics.
3. Issue finding: the synthetic CSV goes through the normal import (checks, de-identification,
   save) into a fresh SQLite database in OUT_DIR. The template (gold) labels are loaded as
   the labels, so grouping is tested on its own, then issues are built with the sentence
   embedder and keyword names. Counts how many of the 8 built-in problems are found.
4. FR5 and the rising flag: the staff-only and patient-only problems are counted by source
   with the same query /compare runs, restricted to the issue holding most of that problem,
   and marked with the same rule. The rising problem's issue must be flagged.
5. NFR3 timing: import and issue building for 1,000 comments, plus baseline labelling.
6. Recovery on a few other generator seeds, to show how much the step 3 count moves when
   the wording changes.

With --llm MODEL it also scores that model, through LiteLLM, on the held-out split. That
needs the provider's API key and costs money, so it is off by default.

Writes results.json and results.md to OUT_DIR, with library versions, Python version,
seeds, the git commit, and every number next to its P3 target.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import kaizen.classify  # noqa: F401  (sets LiteLLM to its bundled model list before anything imports it)

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
DATA = BACKEND / "tests" / "data"
GENERATOR = BACKEND / "scripts" / "make_synthetic.py"
GUIDE = REPO / "docs" / "labelling-guide.md"
EXTRA_SEEDS = (1, 2, 3, 4)
TIMING_COMMENTS = 1000
NFR3_SECONDS = 15 * 60
RECOVERY_TARGET = 6

LIBRARIES = (
    "presidio-analyzer", "spacy", "en_core_web_lg", "scikit-learn", "numpy", "fastembed",
    "onnxruntime", "umap-learn", "sqlalchemy", "fastapi", "litellm",
)


@dataclass
class Check:
    id: str
    what: str
    value: float | int | None
    target: str
    met: bool
    shown: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "what": self.what, "value": self.value, "shown": self.shown, "target": self.target, "met": self.met}


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _versions() -> dict[str, str | None]:
    found = {}
    for name in LIBRARIES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


def _environment(data_dir: Path) -> dict:
    from kaizen.classify.prompt import PROMPT_VERSION
    from kaizen.issues.embed import DEFAULT_MODEL

    status = _git("status", "--porcelain")
    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(status) if status is not None else None,
        "libraries": _versions(),
        "embedding_model": DEFAULT_MODEL,
        "label_prompt_version": PROMPT_VERSION,
        "labelling_guide_sha256": _sha256(GUIDE),
        "data_files_sha256": {p.name: _sha256(p) for p in sorted(data_dir.glob("synthetic*"))},
    }


# 1. De-identification


def _deid(test_set: Path) -> tuple[list[Check], dict]:
    from kaizen.deid.evaluate import MUST_FIND_ALL, evaluate, load

    report = evaluate(load(test_set))
    per_type = {t: {"found": report.found[t], "total": report.total[t], "recall": report.recall_for(t)} for t in sorted(report.total)}
    ids_found = all(report.found[t] == report.total[t] for t in MUST_FIND_ALL)
    units_removed = report.keep_removed.get("UNIT", 0)
    checks = [
        Check("deid_recall", "De-identification: details found", report.recall, ">= 95%", report.recall >= 0.95, f"{report.recall:.1%}"),
        Check(
            "deid_ids_all_found", "De-identification: every ID number, phone and email found",
            sum(report.found[t] for t in MUST_FIND_ALL), f"all {sum(report.total[t] for t in MUST_FIND_ALL)}", ids_found,
            f"{sum(report.found[t] for t in MUST_FIND_ALL)} of {sum(report.total[t] for t in MUST_FIND_ALL)}",
        ),
        Check(
            "deid_over_removal", "De-identification: tags that remove non-personal text",
            report.over_removal_rate, "< 5%", report.over_removal_rate < 0.05, f"{report.over_removal_rate:.1%}",
        ),
        Check("deid_units_removed", "De-identification: unit names removed", units_removed, "0", units_removed == 0, str(units_removed)),
    ]
    detail = {
        "test_set": test_set.name,
        "comments": len(load(test_set)),
        "per_type": per_type,
        "tags": report.tags,
        "over_removed": report.over_removed,
        "keep_removed": dict(report.keep_removed),
        "keep_total": dict(report.keep_total),
        "missed": [{"comment": i, "type": t} for i, t, _ in report.misses],  # ids only, no comment text
    }
    return checks, detail


# 2. Labelling


def _labelling_checks(prefix: str, who: str, result: dict) -> list[Check]:
    from kaizen.classify.metrics import TARGETS

    names = {
        "sentiment_macro_f1": "sentiment macro F1",
        "category_micro_f1": "problem category micro F1",
        "stage_accuracy": "stage of care accuracy",
        "urgency_high_recall": "share of high-urgency comments flagged high",
    }
    checks = []
    for key, target in TARGETS.items():
        value = result[key]
        shown = "n/a" if value is None else (f"{value:.1%}" if key in ("stage_accuracy", "urgency_high_recall") else f"{value:.3f}")
        target_shown = f">= {target:.0%}" if key in ("stage_accuracy", "urgency_high_recall") else f">= {target:.2f}"
        checks.append(Check(f"{prefix}_{key}", f"{who}: {names[key]}", value, target_shown, bool(result["meets_target"][key]), shown))
    return checks


def _baseline(train_path: Path, test_path: Path) -> tuple[list[Check], dict, object]:
    from kaizen.classify.__main__ import load_labelled
    from kaizen.classify.baseline import BaselineLabeller
    from kaizen.classify.metrics import score

    train_items, train_labels = load_labelled(train_path)
    test_items, gold = load_labelled(test_path)
    labeller = BaselineLabeller().fit(train_items, [train_labels[i.id] for i in train_items])
    result = score(gold, labeller.label(test_items))
    result.update(labeller=labeller.name, version=labeller.version, train=len(train_items), test=len(test_items))
    return _labelling_checks("baseline", "TF-IDF baseline", result), result, labeller


def _llm(model: str, test_path: Path, batch_size: int = 10) -> tuple[list[Check], dict]:
    from kaizen.classify.__main__ import load_labelled
    from kaizen.classify.llm import LabelError, LLMLabeller
    from kaizen.classify.metrics import score

    items, gold = load_labelled(test_path)
    labeller = LLMLabeller(model=model)
    predicted, failed = {}, 0
    for i in range(0, len(items), batch_size):
        try:
            predicted.update(labeller.label(items[i : i + batch_size]))
        except LabelError:
            failed += 1
    result = score(gold, predicted)
    result.update(labeller=labeller.name, prompt_version=labeller.version, failed_batches=failed)
    return _labelling_checks("llm", f"LLM {labeller.name}", result), result


# 3 and 4. Issues, FR5 and the rising flag


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fresh_db(path: Path):
    from kaizen.db import make_engine, make_sessionmaker

    path.unlink(missing_ok=True)
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    return engine, make_sessionmaker(engine)


def _import_csv(session, data: bytes):
    from kaizen.db import Channel
    from kaizen.ingest.csv_import import parse_csv
    from kaizen.ingest.save import save_feedback

    rows, errors = parse_csv(data)
    save_feedback(session, rows, Channel.CSV, None, rows_rejected=len(errors))
    return rows, errors


def _store_labels(session, labels_by_comment: dict[int, dict], labeller: str, version: str) -> None:
    from kaizen.db import CommentLabel, LabelStatus

    for comment_id, values in labels_by_comment.items():
        session.add(
            CommentLabel(comment_id=comment_id, status=LabelStatus.CONFIRMED, suggested=values, labeller=labeller, prompt_version=version, **values)
        )
    session.commit()


def _gold_values(row: dict) -> dict:
    return {"sentiment": row["sentiment"], "categories": sorted(row["categories"]), "stage": row["stage"], "urgency": row["urgency"]}


def _only_by_source(session, comment_ids: list[int]) -> tuple[int, int, str | None]:
    """The /compare query and its `only` rule, for one issue's comments."""
    from sqlalchemy import select

    from kaizen.api.compare import _only
    from kaizen.db import Comment, CommentLabel, Source

    query = (
        select(Comment.source, Comment.unit, CommentLabel.stage, CommentLabel.categories)
        .join(CommentLabel, CommentLabel.comment_id == Comment.id)
        .where(Comment.id.in_(comment_ids))
    )
    counts = Counter(source for source, *_ in session.execute(query))
    patient, staff = counts[Source.PATIENT_FAMILY], counts[Source.STAFF]
    return patient, staff, _only(patient, staff)


def _issues(data_dir: Path, out_dir: Path, make_embedder: Callable, min_size: int | None) -> tuple[list[Check], dict]:
    from sqlalchemy import select

    from kaizen.api.compare import compare
    from kaizen.db import Comment, Issue, IssueComment, Role, User
    from kaizen.issues.build import build_issues
    from kaizen.issues.evaluate import TOP_N, planted_recovery
    from kaizen.issues.name import KeywordNamer

    gold = _read_jsonl(data_dir / "synthetic.jsonl")
    problems = json.loads((data_dir / "synthetic_problems.json").read_text(encoding="utf-8"))["problems"]
    engine, Session = _fresh_db(out_dir / "kaizen-eval.db")
    try:
        with Session() as session:
            rows, errors = _import_csv(session, (data_dir / "synthetic.csv").read_bytes())
            comments = session.scalars(select(Comment).order_by(Comment.id)).all()
            if errors or len(comments) != len(gold):
                raise SystemExit(f"import kept {len(comments)} of {len(gold)} rows, {len(errors)} rejected")
            planted_of = {c.id: g["planted"] for c, g in zip(comments, gold)}
            changed_by_deid = sum(c.text != g["text"] for c, g in zip(comments, gold))
            _store_labels(session, {c.id: _gold_values(g) for c, g in zip(comments, gold)}, "gold:synthetic-templates", "template")

            run = build_issues(session, make_embedder(), KeywordNamer(), min_cluster_size=min_size)
            issues = session.scalars(select(Issue).where(Issue.run_id == run.id).order_by(Issue.rank)).all()
            members = {
                i.id: session.scalars(select(IssueComment.comment_id).where(IssueComment.issue_id == i.id).order_by(IssueComment.comment_id)).all()
                for i in issues
            }

            # planted_recovery wants positions into one list, as the CLI gives it.
            grouped_ids = _grouped_ids(session)
            position = {cid: n for n, cid in enumerate(grouped_ids)}
            planted = [planted_of[cid] for cid in grouped_ids]
            found_like = [SimpleNamespace(cluster=SimpleNamespace(members=[position[c] for c in members[i.id]])) for i in issues]
            recovery = planted_recovery(found_like, planted)

            problem_rows = []
            for p in problems:
                best = _best_issue(p["id"], issues, members, planted_of)
                row = {**p, "rank_found": recovery["rank_of"].get(p["id"])}
                if best:
                    issue, n = best
                    patient, staff, only = _only_by_source(session, members[issue.id])
                    row.update(
                        best_issue_rank=issue.rank, best_issue_name=issue.name, best_issue_size=issue.size,
                        best_issue_holds=n, purity=round(n / issue.size, 3), coverage=round(n / p["comments"], 3),
                        issue_patient=patient, issue_staff=staff, issue_only=only, issue_rising=issue.rising,
                    )
                problem_rows.append(row)

            evaluator = User(username="evaluation", password_hash="!", role=Role.QI)
            session.add(evaluator)
            session.commit()
            compare_cells = {
                by: [r for r in compare(by=by, unit=None, date_from=None, date_to=None, user=evaluator, session=session)["rows"] if r["only"]]
                for by in ("category", "stage", "unit")
            }
            top = [
                {
                    "rank": i.rank, "name": i.name, "size": i.size, "score": i.score, "patient": i.patient_count, "staff": i.staff_count,
                    "rising": i.rising, "main_planted": _main_planted(members[i.id], planted_of),
                }
                for i in issues[:TOP_N]
            ]
    finally:
        engine.dispose()

    by_id = {r["id"]: r for r in problem_rows}
    staff_only = [r for r in problem_rows if r["reporters"] == "staff"]
    patient_only = [r for r in problem_rows if r["reporters"] == "patient_family"]
    both = [r for r in problem_rows if r["reporters"] == "both"]
    rising = [r for r in problem_rows if r["rising"]]
    other_rising = [t for t in top if t["rising"] and not (t["main_planted"] and by_id[t["main_planted"]]["rising"])]

    def one_group(rows: list[dict], expect: str) -> tuple[int, int]:
        return sum(r.get("issue_only") == expect for r in rows), len(rows)

    s_ok, s_n = one_group(staff_only, "staff")
    p_ok, p_n = one_group(patient_only, "patient")
    both_ok = sum(r.get("issue_only") is None and "issue_only" in r for r in both)
    rising_ok = sum(bool(r.get("issue_rising")) for r in rising)
    checks = [
        Check("issues_recovered", "Issues: built-in problems found in the top 15", recovery["found"], f">= {RECOVERY_TARGET} of {recovery['planted']}",
              recovery["found"] >= RECOVERY_TARGET, f"{recovery['found']} of {recovery['planted']}"),
        Check("fr5_staff_only", "FR5: staff-only problem marked as staff only", s_ok, f"{s_n} of {s_n}", s_ok == s_n, f"{s_ok} of {s_n}"),
        Check("fr5_patient_only", "FR5: patient-only problem marked as patients only", p_ok, f"{p_n} of {p_n}", p_ok == p_n, f"{p_ok} of {p_n}"),
        Check("fr5_both_not_marked", "FR5: problems both groups report are not marked one-group", both_ok, f"{len(both)} of {len(both)}",
              both_ok == len(both), f"{both_ok} of {len(both)}"),
        Check("fr4_rising_flagged", "FR4: built-in rising problem flagged", rising_ok, f"{len(rising)} of {len(rising)}",
              rising_ok == len(rising), f"{rising_ok} of {len(rising)}"),
    ]
    detail = {
        "database": "kaizen-eval.db",
        "comments_imported": len(rows),
        "comments_changed_by_deid": changed_by_deid,
        "min_cluster_size": run.min_cluster_size,
        "comments_grouped": run.comments_used,
        "outliers": run.outliers,
        "issues": len(issues),
        "rank_of": recovery["rank_of"],
        "problems": problem_rows,
        "top_issues": top,
        "other_rising_in_top": len(other_rising),
        "compare_only_cells": compare_cells,
    }
    return checks, detail


def _grouped_ids(session) -> list[int]:
    """The comments build_issues grouped, in its order: everything not labelled positive."""
    from kaizen.issues.build import load

    return load(session)[0]


def _best_issue(problem: str, issues, members, planted_of) -> tuple[object, int] | None:
    best = None
    for issue in issues:
        n = sum(planted_of[c] == problem for c in members[issue.id])
        if n and (best is None or n > best[1]):
            best = (issue, n)
    return best


def _main_planted(comment_ids: list[int], planted_of: dict[int, str | None]) -> str | None:
    counts = Counter(planted_of[c] for c in comment_ids if planted_of[c])
    if not counts:
        return None
    problem, n = counts.most_common(1)[0]
    return problem if n / len(comment_ids) >= 0.5 else None


# 5. NFR3 timing


def _first_rows_csv(path: Path, n: int) -> bytes:
    reader = csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline=""))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for i, row in enumerate(reader):
        if i > n:
            break
        writer.writerow(row)
    return out.getvalue().encode("utf-8")


def _timing(data_dir: Path, out_dir: Path, make_embedder: Callable, labeller, n: int, min_size: int | None) -> tuple[list[Check], dict]:
    from sqlalchemy import select

    from kaizen.classify.prompt import CommentInput
    from kaizen.db import Comment
    from kaizen.issues.build import build_issues
    from kaizen.issues.name import KeywordNamer

    data = _first_rows_csv(data_dir / "synthetic.csv", n)
    engine, Session = _fresh_db(out_dir / "kaizen-timing.db")
    try:
        with Session() as session:
            start = time.perf_counter()
            rows, _ = _import_csv(session, data)
            imported = time.perf_counter() - start

            start = time.perf_counter()
            comments = session.scalars(select(Comment).order_by(Comment.id)).all()
            labels = labeller.label([CommentInput(c.id, c.text, c.source.value, c.unit) for c in comments])
            _store_labels(session, {cid: lab.as_dict() for cid, lab in labels.items()}, labeller.name, labeller.version)
            labelled = time.perf_counter() - start

            start = time.perf_counter()
            run = build_issues(session, make_embedder(), KeywordNamer(), min_cluster_size=min_size)
            built = time.perf_counter() - start
    finally:
        engine.dispose()
    total = imported + labelled + built
    detail = {
        "comments": len(rows),
        "import_seconds": round(imported, 2),
        "baseline_label_seconds": round(labelled, 2),
        "build_issues_seconds": round(built, 2),
        "total_seconds": round(total, 2),
        "comments_grouped": run.comments_used,
        "machine": platform.processor() or platform.machine(),
    }
    return [
        Check("nfr3_seconds", f"NFR3: import, baseline labels and issue building for {len(rows)} comments", round(total, 1),
              f"<= {NFR3_SECONDS} s", total <= NFR3_SECONDS, f"{total:.0f} s")
    ], detail


# 6. Other seeds


def _load_generator():
    if not GENERATOR.exists():
        return None
    spec = importlib.util.spec_from_file_location("make_synthetic", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("make_synthetic", module)  # dataclasses look the module up while it loads
    spec.loader.exec_module(module)
    return module


def _recovery_rows(rows: list[dict], embedder, min_size: int | None) -> dict:
    from kaizen.issues.evaluate import planted_recovery
    from kaizen.issues.pipeline import find_issues
    from kaizen.issues.rank import IssueComment as RankInput

    grouped = [r for r in rows if r["sentiment"] != "positive"]
    texts = [r["text"] for r in grouped]
    comments = [
        RankInput(r["id"], r["source"], r["sentiment"], r["urgency"], r["stage"], tuple(r["categories"]), date.fromisoformat(r["date"]))
        for r in grouped
    ]
    found, _ = find_issues(texts, comments, embedder.embed(texts), min_size)
    return planted_recovery(found, [r["planted"] for r in grouped])


def _other_seeds(seeds, n: int, embedder, min_size: int | None) -> dict | None:
    generator = _load_generator()
    if generator is None or not seeds:
        return None
    runs = []
    for seed in seeds:
        result = _recovery_rows(generator.generate(seed, n), embedder, min_size)
        runs.append({"seed": seed, "found": result["found"], "missed": [p for p, r in result["rank_of"].items() if r is None]})
    found = [r["found"] for r in runs]
    return {"comments_per_seed": n, "runs": runs, "min": min(found), "median": statistics.median(found), "max": max(found)}


# Putting it together


def run(
    out_dir: Path,
    data_dir: Path = DATA,
    deid_set: Path | None = None,
    make_embedder: Callable | None = None,
    llm: str | None = None,
    timing_comments: int = TIMING_COMMENTS,
    extra_seeds=EXTRA_SEEDS,
    min_size: int | None = None,
) -> dict:
    if make_embedder is None:
        from kaizen.issues.embed import SentenceEmbedder

        make_embedder = SentenceEmbedder
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads((data_dir / "synthetic_problems.json").read_text(encoding="utf-8"))

    checks: list[Check] = []
    details: dict = {}
    started = time.perf_counter()
    c, d = _deid(deid_set or DATA / "deid_test_set.jsonl")
    checks += c
    details["deid"] = d
    c, d, baseline = _baseline(data_dir / "synthetic_train.jsonl", data_dir / "synthetic_test.jsonl")
    checks += c
    details["baseline"] = d
    if llm:
        c, d = _llm(llm, data_dir / "synthetic_test.jsonl")
        checks += c
        details["llm"] = d
    c, d = _issues(data_dir, out_dir, make_embedder, min_size)
    checks += c
    details["issues"] = d
    c, d = _timing(data_dir, out_dir, make_embedder, baseline, timing_comments, min_size)
    checks += c
    details["timing"] = d
    details["other_seeds"] = _other_seeds(extra_seeds, meta["n"], make_embedder(), min_size)

    results = {
        "environment": _environment(data_dir),
        "seeds": {"data": meta["seed"], "split": f"{meta['seed']}-split", "umap": 42, "other_data_seeds": list(extra_seeds)},
        "data": {"comments": meta["n"], "test_split": meta["test_size"], "problems": meta["problems"]},
        "checks": [c.as_dict() for c in checks],
        "details": details,
        "run_seconds": round(time.perf_counter() - started, 1),
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    (out_dir / "results.md").write_text(to_markdown(results), encoding="utf-8")
    return results


def _table(header: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join("" if v is None else str(v) for v in row) + " |" for row in rows]
    return lines


def to_markdown(results: dict) -> str:
    env, details = results["environment"], results["details"]
    commit = (env["git_commit"] or "unknown")[:12] + (" (uncommitted changes)" if env["git_dirty"] else "")
    met = sum(c["met"] for c in results["checks"])
    lines = [
        "# Kaizen evaluation results",
        "",
        f"Run {env['run_at']} on Python {env['python']} ({env['platform']}), commit {commit}. "
        f"{met} of {len(results['checks'])} checks met their P3 target. Took {results['run_seconds']} s.",
        "",
        "## Against the P3 targets",
        "",
        *_table(["Check", "Result", "Target", "Met"], [[c["what"], c["shown"], c["target"], "met" if c["met"] else "MISSED"] for c in results["checks"]]),
        "",
        "Labelling scores are on the 300 held-out synthetic comments, whose labels come from the same",
        "templates as the training split. The baseline sees the same sentences with different fillers,",
        "so its scores are an upper bound and say little about real comments. The hand-labelled test",
        "set (P3 section 3.1) is the real test for FR3.",
        "",
    ]

    deid = details["deid"]
    lines += ["## De-identification", "", f"{deid['comments']} comments in `{deid['test_set']}`.", ""]
    lines += _table(["Type", "Found", "Total", "Recall"], [[t, v["found"], v["total"], f"{v['recall']:.1%}"] for t, v in deid["per_type"].items()])
    lines += ["", f"{deid['over_removed']} of {deid['tags']} tags removed text that is not personal.", ""]

    base = details["baseline"]
    lines += [
        "## Labelling baseline",
        "",
        f"{base['labeller']} version {base['version']}, trained on {base['train']} and scored on {base['test']} comments. "
        f"Category macro F1 {base['category_macro_f1']:.3f}, stage macro F1 {base['stage_macro_f1']:.3f}, "
        f"urgency accuracy {base['urgency_accuracy']:.1%}.",
        "",
        *_table(["Category", "F1"], [[k, f"{v:.3f}"] for k, v in base["category_f1"].items()]),
        "",
    ]
    if "llm" in details:
        llm = details["llm"]
        lines += [f"LLM {llm['labeller']} (prompt {llm['prompt_version']}): {llm['missing']} comments missing, {llm['failed_batches']} failed batches.", ""]

    iss = details["issues"]
    lines += [
        "## Issues",
        "",
        f"{iss['comments_imported']} comments imported through the CSV path ({iss['comments_changed_by_deid']} changed by",
        f"de-identification), gold labels loaded, {iss['comments_grouped']} negative and neutral comments grouped",
        f"with a minimum issue size of {iss['min_cluster_size']}: {iss['issues']} issues and {iss['outliers']} outliers.",
        "A built-in problem counts as found when a top-15 issue is at least half its comments and holds",
        "at least 30% of them (`kaizen.issues.evaluate`).",
        "",
        *_table(
            ["Problem", "Reported by", "Comments", "Found at rank", "Best issue", "Holds", "Purity", "Patients", "Staff", "Marked only", "Rising"],
            [
                [p["id"], p["reporters"], p["comments"], p["rank_found"] or "not found", p.get("best_issue_rank"), p.get("best_issue_holds"),
                 f"{p['purity']:.0%}" if "purity" in p else None, p.get("issue_patient"), p.get("issue_staff"), p.get("issue_only") or "",
                 "yes" if p.get("issue_rising") else ""]
                for p in iss["problems"]
            ],
        ),
        "",
        "Top 15 issues:",
        "",
        *_table(["Rank", "Name (keywords)", "Size", "Score", "Patients", "Staff", "Rising", "Mostly"],
                [[t["rank"], t["name"], t["size"], t["score"], t["patient"], t["staff"], "yes" if t["rising"] else "", t["main_planted"] or "mixed or background"]
                 for t in iss["top_issues"]]),
        "",
        f"Top-15 issues flagged rising that are not the rising problem: {iss['other_rising_in_top']}.",
        "",
        "FR5 is checked per issue: the /compare query counts the issue's comments by source and its",
        "`only` rule marks them. /compare itself groups by category, stage and unit, and on the whole",
        "data set these cells are marked one-group: "
        + "; ".join(f"by {by}: " + (", ".join(f"{r['key']} ({r['only']})" for r in rows) or "none") for by, rows in iss["compare_only_cells"].items())
        + ".",
        "",
    ]

    t = details["timing"]
    lines += [
        "## Timing (NFR3)",
        "",
        *_table(["Step", "Seconds"], [["Import (checks, de-identification, save)", t["import_seconds"]],
                                      ["Labels from the TF-IDF baseline", t["baseline_label_seconds"]],
                                      ["Issue building (embedding model load, grouping, names)", t["build_issues_seconds"]],
                                      ["Total", t["total_seconds"]]]),
        "",
        f"{t['comments']} comments on {t['machine']}. LLM labelling is not timed, since the default run uses no",
        "API key; the 15 minute budget in P3 also has to cover it.",
        "",
    ]

    other = details.get("other_seeds")
    if other:
        lines += [
            "## Recovery on other generator seeds",
            "",
            f"Same templates, different draws of {other['comments_per_seed']} comments, gold labels, no database.",
            f"Found {other['min']} to {other['max']} of 8 (median {other['median']}).",
            "",
            *_table(["Seed", "Found", "Missed"], [[r["seed"], r["found"], ", ".join(r["missed"])] for r in other["runs"]]),
            "",
        ]

    lines += [
        "## Versions and seeds",
        "",
        f"Data seed {results['seeds']['data']}, split seed `{results['seeds']['split']}`, UMAP seed {results['seeds']['umap']}. "
        f"Embedding model {env['embedding_model']}. Label prompt version {env['label_prompt_version']}. "
        f"Labelling guide sha256 {(env['labelling_guide_sha256'] or 'missing')[:12]}.",
        "",
        *_table(["Library", "Version"], [[k, v or "not installed"] for k, v in env["libraries"].items()]),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kaizen.evaluate", description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--data", type=Path, default=DATA, help="folder with the synthetic files")
    parser.add_argument("--llm", metavar="MODEL", help="also score this LiteLLM model on the held-out split (needs its API key)")
    parser.add_argument("--timing-comments", type=int, default=TIMING_COMMENTS)
    parser.add_argument("--other-seeds", type=int, nargs="*", default=list(EXTRA_SEEDS))
    parser.add_argument("--min-size", type=int, help="smallest issue (default: 2%% of the comments, at least 8)")
    args = parser.parse_args()

    results = run(args.out_dir, args.data, llm=args.llm, timing_comments=args.timing_comments, extra_seeds=args.other_seeds, min_size=args.min_size)
    print((args.out_dir / "results.md").read_text(encoding="utf-8"))
    missed = [c["id"] for c in results["checks"] if not c["met"]]
    print(f"missed: {', '.join(missed)}" if missed else "every check met its target")


if __name__ == "__main__":
    main()
