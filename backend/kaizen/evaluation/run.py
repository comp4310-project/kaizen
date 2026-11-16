"""Run P3 checks using real import, models, grouping and backend endpoints.

The default model is the existing TF-IDF baseline trained only on synthetic training
scenarios. No predictions are copied from truth. LLM mode needs provider credentials.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import secrets
import tempfile
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from kaizen.api.app import create_app
from kaizen.api.auth import hash_password
from kaizen.classify.baseline import BaselineLabeller
from kaizen.classify.labels import Labels
from kaizen.classify.metrics import TARGETS, score
from kaizen.classify.prompt import CommentInput
from kaizen.classify.run import label_comments
from kaizen.db import Comment, CommentLabel, Issue, IssueComment, Role, User
from kaizen.evaluation.generate import SEED, audit, digest
from kaizen.evaluation.report import check, environment, save, unavailable
from kaizen.issues.build import build_issues
from kaizen.issues.embed import SentenceEmbedder
from kaizen.issues.evaluate import planted_recovery, rating_sheet
from kaizen.issues.name import KeywordNamer


def read_dataset(folder):
    rows = list(csv.DictReader((folder / "comments.csv").open(encoding="utf-8", newline="")))
    truth = [json.loads(line) for line in (folder / "truth.jsonl").read_text().splitlines() if line]
    manifest = json.loads((folder / "manifest.json").read_text())
    if digest(folder / "comments.csv") != manifest["csv_sha256"] or digest(folder / "truth.jsonl") != manifest["truth_sha256"]:
        raise ValueError("dataset hashes differ from manifest; regenerate together")
    if len(rows) != len(truth) or [t["row_id"] for t in truth] != list(range(1, len(rows) + 1)):
        raise ValueError("truth must match every CSV row in order")
    train = {t["scenario"] for t in truth if t["split"] == "train"}
    test = {t["scenario"] for t in truth if t["split"] == "test"}
    if train & test:
        raise ValueError("narrative seed leakage across train/test")
    return rows, truth


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    w = csv.DictWriter(stream, fieldnames=["text", "source", "unit", "date"])
    w.writeheader()
    w.writerows(rows)
    return stream.getvalue().encode()


def client_for(path):
    app = create_app(f"sqlite:///{path}")
    password = secrets.token_urlsafe(24)
    with app.state.sessionmaker() as session:
        session.add(User(username="evaluation", password_hash=hash_password(password), role=Role.QI))
        session.commit()
    client = TestClient(app)
    reply = client.post("/auth/login", json={"username": "evaluation", "password": password})
    reply.raise_for_status()
    headers = {"Authorization": f"Bearer {reply.json()['token']}"}
    return app, client, headers


def import_rows(client, headers, rows):
    reply = client.post("/imports", headers=headers, files={"file": ("synthetic.csv", csv_bytes(rows), "text/csv")})
    reply.raise_for_status()
    result = reply.json()
    if result["saved"] != len(rows) or result["rejected"]:
        raise ValueError("import rejected synthetic rows")
    return result


def comments(session):
    return list(session.scalars(select(Comment).order_by(Comment.id)))


def inputs(saved):
    return [CommentInput(id=c.id, text=c.text, source=c.source.value, unit=c.unit) for c in saved]


def label_metrics(gold, predicted):
    if not gold:
        return unavailable("no completed human annotations")
    result = score(gold, predicted)
    result["targets"] = {k: check(result[k], target) for k, target in TARGETS.items()}
    return result


def deid_report(path):
    from kaizen.deid.evaluate import MUST_FIND_ALL, evaluate, load
    items = load(path)
    result = evaluate(items)
    return {
        "comments": len(items), "details": sum(result.total.values()),
        "recall": check(result.recall, .95),
        "mandatory_types": {k: check(result.recall_for(k) if result.total[k] else None, 1, operator="==") for k in MUST_FIND_ALL},
        "over_removal": check(result.over_removal_rate, .05, operator="<"),
        "unit_names_removed": check(result.keep_removed["UNIT"] if result.keep_total["UNIT"] else None, 0, operator="=="),
        "found_by_type": dict(result.found), "total_by_type": dict(result.total),
        "tags": result.tags, "extra_tags": result.over_removed,
    }


def export_annotation_sample(saved, truth, folder):
    eligible = [i for i, t in enumerate(truth) if t["split"] == "test"]
    random.Random(SEED).shuffle(eligible)
    if len(eligible) < 400:
        raise ValueError("need 400 untouched rows for human annotation")
    # No model predictions or synthetic intent fields on the annotation sheet.
    for filename, positions in [("calibration-100.csv", eligible[:100]), ("heldout-300.csv", eligible[100:400])]:
        with (folder / filename).open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["row_id", "text", "source", "unit", "sentiment", "categories", "stage", "urgency"])
            for i in positions:
                c = saved[i]
                w.writerow([truth[i]["row_id"], c.text, c.source.value, c.unit, "", "", "", ""])


def issue_results(session, saved, truth, run_id):
    issues = list(session.scalars(select(Issue).where(Issue.run_id == run_id).order_by(Issue.rank)))
    index = {c.id: i for i, c in enumerate(saved)}
    found, membership = [], [-1] * len(saved)
    for issue in issues:
        ids = list(session.scalars(select(IssueComment.comment_id).where(IssueComment.issue_id == issue.id)))
        positions = [index[i] for i in ids]
        found.append(SimpleNamespace(cluster=SimpleNamespace(members=positions)))
        for i in positions:
            membership[i] = issue.rank
    # All planted rows stay in the denominator, even those mislabelled as positive.
    recovery = planted_recovery(found, [t["planted"] for t in truth])
    recovery["target"] = check(recovery["found"], 6)
    pattern = {}
    for name in ("discharge_medication", "night_noise", "transport"):
        rank = recovery["rank_of"].get(name)
        issue = next((i for i in issues if i.rank == rank), None)
        if issue is None:
            pattern[name] = {"status": "FAIL", "reason": "planted issue not recovered in top 15"}
            continue
        valid = (issue.patient_count > 0 and issue.staff_count > 0) if name == "discharge_medication" else (
            issue.patient_count > 0 and issue.staff_count == 0 if name == "night_noise" else issue.rising)
        pattern[name] = {"status": "PASS" if valid else "FAIL", "rank": rank,
                         "patient": issue.patient_count, "staff": issue.staff_count, "rising": issue.rising}
    from sklearn.metrics import adjusted_rand_score
    planted = [i for i, t in enumerate(truth) if t["planted"]]
    ari = adjusted_rand_score([truth[i]["planted"] for i in planted], [membership[i] for i in planted])
    return {"recovery": recovery, "patterns": pattern,
            "adjusted_rand_index_planted": ari, "ari_note": "diagnostic only; outliers/unselected rows share -1",
            "issues": len(issues), "unassigned_rows": membership.count(-1),
            "human_quality": unavailable("two members must rate ten comments from each top issue")}


def api_checks(client, headers, session, repeats=10):
    issues = list(session.scalars(select(Issue).order_by(Issue.rank)))
    endpoints = ["/issues", "/comments?limit=50", "/compare?by=category", "/compare?by=stage",
                 "/compare?by=unit", "/suggestions"]
    if issues:
        endpoints.extend([f"/issues/{issues[0].id}/comments", f"/issues/{issues[0].id}/comments?format=csv"])
    result = {}
    for endpoint in endpoints:
        elapsed, statuses = [], []
        for _ in range(repeats):
            started = time.perf_counter()
            response = client.get(endpoint, headers=headers)
            elapsed.append(time.perf_counter() - started)
            statuses.append(response.status_code)
        result[endpoint] = {"samples": repeats, "seconds": elapsed,
                            "p50_seconds": float(np.percentile(elapsed, 50)),
                            "p95_seconds": float(np.percentile(elapsed, 95)),
                            "maximum": check(max(elapsed), 2, operator="<="),
                            "http_200": check(all(s == 200 for s in statuses), True, operator="==")}
    # Independently reconstruct all comparison buckets from actual saved predictions.
    labelled = list(session.execute(select(Comment, CommentLabel).join(CommentLabel, CommentLabel.comment_id == Comment.id)))
    comparisons = {}
    for by in ("category", "stage", "unit"):
        expected = {}
        total = Counter()
        for c, lab in labelled:
            group = "patient" if c.source.value == "patient_family" else "staff"
            total[group] += 1
            keys = lab.categories if by == "category" else [lab.stage if by == "stage" else c.unit]
            for key in keys:
                expected.setdefault(key, Counter())[group] += 1
        response = client.get(f"/compare?by={by}", headers=headers).json()
        expected_rows = {k: {"patient": v["patient"], "staff": v["staff"],
                            "only": "patient" if not v["staff"] else "staff" if not v["patient"] else None}
                         for k, v in expected.items()}
        actual = {row["key"]: {k: row[k] for k in ("patient", "staff", "only")} for row in response["rows"]}
        comparisons[by] = check(actual == expected_rows and response["totals"] == dict(total), True, operator="==")
    return {"scope": "in-process FastAPI TestClient; real SQLite and routes; no network/browser/rendering or MySQL",
            "endpoints": result, "comparison_integrity": comparisons,
            "issue_detail_covered": bool(issues), "suggestion_rows": len(client.get("/suggestions", headers=headers).json()["suggestions"])}


def benchmark(rows, labeller, embedder, repeats, batch_size, workers, min_cluster_size):
    if len(rows) < 1000:
        raise ValueError("NFR3 needs at least 1000 comments")
    indices = random.Random(SEED).sample(range(len(rows)), 1000)
    selected = [rows[i] for i in indices]
    with tempfile.TemporaryDirectory(prefix="kaizen-benchmark-", ignore_cleanup_errors=True) as temporary:
        app, client, headers = client_for(Path(temporary) / "benchmark.db")
        with client, app.state.sessionmaker() as session:
            started = time.perf_counter()
            imported = import_rows(client, headers, selected)
            after_import = time.perf_counter()
            run = label_comments(session, labeller, batch_size=batch_size, workers=workers)
            after_labels = time.perf_counter()
            issue_run = build_issues(session, embedder, KeywordNamer(), seed=SEED, min_cluster_size=min_cluster_size)
            elapsed = time.perf_counter() - started
            complete = run.labelled == 1000 and run.missed == 0 and run.failed_batches == 0
            result = {
                "rows": 1000, "seed": SEED, "source_groups": dict(Counter(r["source"] for r in selected)),
                "scope": "CSV HTTP import with real de-identification, persisted classification, embedding, clustering and keyword naming",
                "excluded": "baseline training, model setup/download, account setup, suggestions, browser and network latency",
                "model_cache": "warm; full dataset evaluation ran first",
                "database": "temporary SQLite", "labeller": labeller.name, "embedder": embedder.name,
                "namer": "keywords", "batch_size": batch_size, "workers": workers, "min_cluster_size": issue_run.min_cluster_size,
                "import_seconds": after_import-started, "label_seconds": after_labels-after_import,
                "group_seconds": elapsed-(after_labels-started), "total_seconds": elapsed,
                "complete": complete, "labelled": run.labelled, "missed": run.missed,
                "failed_batches": run.failed_batches, "issues_input_rows": issue_run.comments_used,
                "processing_target": check(elapsed if complete else None, 900, operator="<="),
                "dashboard": api_checks(client, headers, session, repeats),
            }
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/synthetic"))
    p.add_argument("--out", type=Path, default=Path("reports/bhavya"))
    p.add_argument("--public-csv", type=Path, help="ignored local extract from fetch_fft_comments.py")
    p.add_argument("--method", choices=["baseline", "llm"], default="baseline")
    p.add_argument("--batch-size", type=int, default=50)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--min-cluster-size", type=int, help="default: 2%% of the grouped comments, at least 8")
    p.add_argument("--api-repeats", type=int, default=10)
    p.add_argument("--skip-benchmark", action="store_true")
    p.add_argument("--skip-grouping", action="store_true", help="partial run if embedding model cannot be downloaded")
    args = p.parse_args()
    if args.min_cluster_size is not None and args.min_cluster_size < 2:
        p.error("minimum cluster size must be at least 2")
    if min(args.batch_size, args.workers, args.api_repeats) < 1:
        p.error("batch size, workers and repeats must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    rows, truth = read_dataset(args.data)
    report = {"environment": environment(), "data": audit(rows, truth),
              "dataset_sha256": digest(args.data / "comments.csv"),
              "configuration": {"seed": SEED, "method": args.method, "batch_size": args.batch_size,
                                "workers": args.workers, "min_cluster_size": args.min_cluster_size or "default"},
              "public_data": unavailable("no licensed public test set with completed HCAT human labels supplied"),
              "human_synthetic": unavailable("400-row blank annotation workflow exported; no human labels supplied"),
              "suggestions": unavailable("no provider credentials or two completed 40-item rating sheets"),
              "usability": unavailable("five-person SUS study belongs to NFR4; see docs/frontend-usability.md")}
    save(args.out, report)
    print("Scoring real de-identification test set...", flush=True)
    report["deidentification"] = deid_report(Path("backend/tests/data/deid_test_set.jsonl"))
    save(args.out, report)
    with tempfile.TemporaryDirectory(prefix="kaizen-evaluate-", ignore_cleanup_errors=True) as temporary:
        app, client, headers = client_for(Path(temporary) / "evaluation.db")
        with client, app.state.sessionmaker() as session:
            print("Importing 2300 synthetic comments through POST /imports...", flush=True)
            started = time.perf_counter()
            report["import"] = import_rows(client, headers, rows)
            report["import"]["seconds"] = time.perf_counter() - started
            saved = comments(session)
            if len(saved) != len(truth):
                raise ValueError("fresh database row mapping failed")
            export_annotation_sample(saved, truth, args.out)
            model_inputs = inputs(saved)
            if args.method == "baseline":
                train = [i for i, t in enumerate(truth) if t["split"] == "train"]
                labeller = BaselineLabeller().fit([model_inputs[i] for i in train],
                                                 [Labels.model_validate(truth[i]) for i in train])
            else:
                from kaizen.classify.llm import LLMLabeller
                labeller = LLMLabeller()
            print(f"Predicting using {labeller.name}...", flush=True)
            run = label_comments(session, labeller, batch_size=args.batch_size, workers=args.workers)
            labels = {lab.comment_id: Labels.model_validate(lab.suggested) for lab in session.scalars(select(CommentLabel))}
            gold = {saved[i].id: Labels.model_validate(t) for i, t in enumerate(truth) if t["split"] == "test"}
            report["synthetic_intent"] = label_metrics(gold, labels)
            report["synthetic_intent"]["labeller"] = labeller.name
            report["synthetic_intent"]["prompt_version"] = labeller.version
            report["synthetic_intent"]["note"] = "scenario-held-out synthetic intent, not the 300 human-labelled P3 test comments"
            report["classification_run"] = vars(run)
            # ID map is explicit; no assumption that CSV row numbers equal DB IDs.
            predictions = [{"row_id": t["row_id"], "prediction": labels[c.id].as_dict() if c.id in labels else None}
                           for c, t in zip(saved, truth)]
            (args.out / "predictions.jsonl").write_text("".join(json.dumps(x) + "\n" for x in predictions), encoding="utf-8")
            if args.public_csv:
                from kaizen.evaluation.public import evaluate_public
                print("Evaluating published FFT sentiment labels separately...", flush=True)
                report["public_data"] = evaluate_public(args.public_csv, labeller, args.batch_size)
            save(args.out, report)
            embedder = None
            if args.skip_grouping:
                report["issues"] = unavailable("grouping explicitly skipped")
            else:
                print("Loading sentence model and building issues from predictions...", flush=True)
                try:
                    started = time.perf_counter()
                    embedder = SentenceEmbedder()
                    issue_run = build_issues(session, embedder, KeywordNamer(), seed=SEED, min_cluster_size=args.min_cluster_size)
                    report["issues"] = issue_results(session, saved, truth, issue_run.id)
                    report["issues"]["min_cluster_size"] = issue_run.min_cluster_size
                    report["issues"]["seconds_including_model_load"] = time.perf_counter() - started
                    report["issues"]["embedder"] = embedder.name
                    cache = Path(os.environ.get("KAIZEN_EMBED_CACHE", "work/model-cache"))
                    report["issues"]["model_files_sha256"] = {
                        str(path.relative_to(cache)): digest(path)
                        for path in sorted(cache.glob("**/snapshots/**/*"))
                        if path.is_file() and path.suffix in (".onnx", ".json")
                    }
                    report["issues"]["namer"] = "keywords"
                    rating_sheet(session, args.out / "issues-to-rate.csv", seed=SEED)
                except Exception as exc:
                    session.rollback()
                    report["issues"] = unavailable(f"grouping failed: {type(exc).__name__}; check model availability")
                    embedder = None
            report["dashboard"] = api_checks(client, headers, session, args.api_repeats)
            save(args.out, report)
            if not args.skip_benchmark and embedder is not None:
                print("Benchmarking 1000 comments through the real pipeline...", flush=True)
                report["performance"] = benchmark(rows, labeller, embedder,
                                                  args.api_repeats, args.batch_size, args.workers, args.min_cluster_size)
            else:
                report["performance"] = unavailable("benchmark skipped or embedding unavailable; import/API timing is partial")
    save(args.out, report)
    print(f"Saved {args.out}/results.json and summary.md", flush=True)


if __name__ == "__main__":
    main()
