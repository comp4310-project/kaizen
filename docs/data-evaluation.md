# Data and evaluation

For submission status and reviewer tasks, see [Bhavya's handoff](bhavya-handoff.md).

Bhavya's P3 Table 8 work is in `backend/kaizen/evaluation/`. The runner uses the existing
de-identification scorer, classifier metrics, baseline, issue recovery scorer and
suggestion scorer. It does not change the import, classifier, grouping or dashboard
implementations owned by other members.

During final integration, main gained a separate 1,200-row fixture and the
`kaizen.evaluate` runner. Both are retained without changes. That runner includes an
isolated grouping experiment using supplied synthetic labels. The 2,300-row experiment
in this guide instead groups actual classifier predictions and keeps its ground truth
outside the processing pipeline. Use the commands below for Bhavya's requested dataset
and prediction-based benchmark; the two fixtures and their scores must not be combined.
Final results were rerun after merging main's de-identification, issue-filtering and
frontend fixes.

## Run it

Use Python 3.12 on Linux or WSL, from the repository root:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-evaluation.lock
.venv/bin/python -m pip install --no-deps -e './backend[dev]'
bash scripts/evaluate.sh --with-public
```

The command regenerates the synthetic data, downloads the existing pinned public extract,
runs evaluation and the 1,000-comment benchmark, runs pytest, and checks repository hygiene.
It needs network access on the first run for packages and the sentence embedding model.
It uses no paid model API by default. Omit `--with-public` for a synthetic-only run.
`KAIZEN_PYTHON` can select another interpreter. The script sets writable caches under
ignored `work/`, a fixed Python hash seed and one UMAP/OpenMP thread.

The default output is [the measured report](../reports/bhavya/results.json) and
[a readable target summary](../reports/bhavya/summary.md). Re-running replaces those
artifacts. Use `--out work/my-run` to keep the submission results. A failed quality target
is a reported FAIL, not a broken command. Unhandled exceptions and failing automated tests return a nonzero exit code. Grouping
errors are caught and recorded as NOT_MEASURED, with the benchmark skipped. Inspect
results.json and summary.md even when the command exits successfully; NOT_MEASURED
never counts as PASS.

Commands for individual steps:

```sh
.venv/bin/python -m kaizen.evaluation.generate
.venv/bin/python -m kaizen.evaluation.run --out work/evaluation
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python scripts/check_repo.py
```

When running Python directly, set the cache and thread variables as in
[scripts/evaluate.sh](../scripts/evaluate.sh). No database server is needed: each run
creates a fresh temporary SQLite database and removes it on exit. Existing project
databases are never altered. Authentication uses a random temporary password that is
neither printed nor saved.

For the deployed LLM configuration, provide the provider key through the environment and
run `bash scripts/evaluate.sh --method llm --batch-size 10 --workers 4 --out work/llm`.
`KAIZEN_LABEL_MODEL` and `KAIZEN_LABEL_EFFORT` select the model through the existing code.
This performs real API calls and incurs provider costs. The submission has no such
measurement because no provider key was available. Issue names use the existing keyword
namer; no suggestion-generation latency is included in the processing benchmark.

## Synthetic data

[comments.csv](../data/synthetic/comments.csv) has only the existing four import columns:
text, source, unit and date. It contains 2,300 fictional comments: 905 patients, 595 family
members, 496 nurses and 304 physicians. Those collapse to 1,500 patient/family and 800
staff comments. All eight permitted units appear. Dates run from September 21 through
November 1, 2026, so the fixture imports before the submission date.

[truth.jsonl](../data/synthetic/truth.jsonl) is a separate evaluation sidecar.
`row_id` is the one-based CSV data row. It is never assumed to be a database ID.
The sidecar records the planted problem, intended source group, trend, week, narrative
seed, train/test split and intended labels. These labels are AI-authored synthetic intent,
not human annotations. A mixed comment receives one of the guide's three sentiment
labels; it does not introduce a fourth label into the application.

| Problem | Patient/family | Staff | Pattern |
|---|---:|---:|---|
| Discharge medication delay | 130 | 90 | Both groups |
| Night noise | 180 | 0 | Patient/family only |
| ED waiting and missing updates | 130 | 70 | ED only |
| Call bell response | 120 | 60 | Both groups |
| Shift handover | 70 | 110 | Both groups |
| Discharge instructions | 120 | 60 | Both groups |
| Cleanliness or equipment | 100 | 80 | Both groups |
| Internal transport delays | 100 | 80 | Increasing |
| Ordinary background | 550 | 250 | Praise, neutral observations and other complaints |

Transport counts across the six weeks are 8, 12, 18, 28, 42 and 72. This is a designed
frequency trend, not evidence about a hospital. Other issue dates are sampled uniformly;
they are not forced to have identical weekly counts.

The fixed seed is 4310. Version 2 applies text-only corrections from the 100-row
quality review; it preserves every original row ID and truth record. The original dataset
and results remain in Git history at commit `1a1ebe5`. Generation uses an AI-authored bank of 190 narrative seeds,
process-specific follow-on details, short and longer forms, family context, occasional
typos and informal phrasing. There are 2,300 unique full texts, 519 comments of at most
15 words, and 800 background comments. Intended sentiments are 326 positive, 202 neutral
and 1,772 negative. Mixed praise/complaint wording occurs among the negative examples.

Realism remains a limitation. Several comments share a narrative seed or a follow-on
sentence. The generator does not produce 2,300 independently authored patient stories.
The audit records the most frequent five-word openings instead of treating uniqueness
as proof of naturalness. Human reviewers should read a source-balanced sample before
claiming resemblance to collected feedback. No real patient account was copied to create
this dataset. These fixtures must never be described as collected survey responses.

The [manifest](../data/synthetic/manifest.json) records counts, parameters and hashes of
both files. Regeneration is byte-for-byte stable with the saved code and seed. The loader
rejects altered files and mismatched row IDs. Synthetic fixtures are public and under
5 MB per file; public-source raw text stays under ignored `data/raw/`.

## Labels and leakage

All imported text passes through the real de-identification function before storage,
training, prediction, embedding, comparison or annotation export. The model receives
de-identified text, source and unit, not planted issue names or intended labels.

The baseline trains on 1,566 rows from training narrative seeds. Its synthetic accuracy
is measured on 734 rows from different narrative seeds. Every variant of a seed stays in
one split. Shared follow-on phrases still make this easier than genuinely independent
hospital data; those phrases should be considered when interpreting scores.

The grouping experiment uses model predictions on the full synthetic dataset. It is a
fixture recovery diagnostic, including training rows, not a held-out human validation of
the entire pipeline. Planted truth is consulted only after clustering. Recovery uses the
existing rule: a top-15 issue must be at least 50% one planted problem and contain at
least 30% of that problem's comments. All planted rows remain in the denominator, including
rows the classifier incorrectly excluded as positive. Target: six of eight.

The report also checks whether the recovered medication issue has both source groups,
the recovered noise issue has patient/family comments only, and the recovered transport
issue is rising. The real comparison endpoint is checked independently against counts
from saved predictions for category, stage and unit. Correct aggregation and correct
semantic issue recovery are separate checks.

## Human evaluation

Each run exports blank `calibration-100.csv` and `heldout-300.csv` files. They come from
the synthetic test split and contain only de-identified text and input metadata. Neither
intended labels nor predictions appear on the sheets. Two members independently label
the same calibration file, refine the guide, and report agreement before touching the
300-row test set. Do not train on those 300 rows or use them as prompt examples.

Enter categories as a JSON array, for example `["communication","safety"]`, or `[]`.
Use the exact other labels in [the labelling guide](labelling-guide.md). Keep separate
rater copies. Adjudicate disagreements to make a final held-out gold sheet.

```sh
.venv/bin/python -m kaizen.evaluation.score agreement work/rater-a.csv work/rater-b.csv --out work/agreement
.venv/bin/python -m kaizen.evaluation.score labels --gold work/heldout-adjudicated.csv --calibration reports/bhavya/calibration-100.csv --predictions reports/bhavya/predictions.jsonl --corpus synthetic --model tfidf-logreg --human-confirmed --out work/human-synthetic
```

The scoring command rejects blank or duplicate annotations. Missing predictions count
against the model. Urgency recall is NOT_MEASURED when the gold sample has no high-urgency
examples. Sentiment macro F1, category micro F1 (plus every category), stage accuracy and
high-urgency recall use the existing scorer and the P3 thresholds. The 300-row sample size
is also checked. `--human-confirmed` is an explicit attestation, not a way to convert
synthetic intent labels into human truth.

For a separately annotated public dataset, use `--corpus public` and its own prediction
file with row IDs from that dataset. Never combine public and synthetic scores.
The existing `python -m kaizen.classify evaluate` also supports prediction/scoring on
de-identified labelled JSONL, including `--method llm` and a separate baseline training
file. Keep development, training and test rows disjoint before using that older command.

The submitted annotation sheets are blank. No human scores, agreement or formal
300-comment accuracy results are claimed.

## Public-data check

The optional public run reuses [the existing FFT fetcher](../backend/scripts/fetch_fft_comments.py),
its source commit, SHA-256 check, MIT-licence record and NEAS See and Convey filter.
This produces 1,625 ambulance-feedback rows, not ward feedback. Of these, 1,388 have
published five-point sentiment labels and 237 do not. The latter are excluded from
sentiment evaluation. Scores 1 and 2 map to positive, 3 to neutral, and 4 and 5 to negative.

The synthetic-trained baseline predicts those de-identified comments independently.
The report contains aggregate metrics and the extract hash only. It does not store raw
public text, comment identifiers or individual predictions. The source does not supply
the required HCAT category, stage or urgency labels, so those public checks remain
NOT_MEASURED. This domain-transfer check is separate from the planned 300 human-labelled
Kaizen test comments.

## Issues and suggestions

`issues-to-rate.csv` samples ten comments from each of the top 15 issues using seed 4310.
Give a copy to each of two reviewers. Fill both yes/no columns on every row.
The issue is good only if both reviewers find at least eight comments about the same
problem and judge its name specific. The scorer rejects missing rows and duplicate pairs.
If fewer than 15 issues exist, its scope is explicitly partial.

```sh
.venv/bin/python -m kaizen.evaluation.score issues work/issues-a.csv work/issues-b.csv --out work/issue-ratings
```

Suggestion collection and blinded sheets already exist in `kaizen.suggest.evaluate` and
the `kaizen.suggest` CLI. Use `python -m kaizen.suggest --help` for collection commands.
Keep its key apart from the rater copies. After two reviewers have rated 40 suggestions
and the matching no-document controls, run:

```sh
.venv/bin/python -m kaizen.evaluation.score suggestions --key work/suggestions-key.csv work/suggestions-a.csv work/suggestions-b.csv --out work/suggestion-ratings
```

The wrapper reuses the existing relevance, actionability, citation-support, unsafe-output
and agreement scoring. It reports the 40-item sample check, 70% scoring five or six,
and zero unsafe outputs. There are no actual generated suggestions or completed rater
sheets in this submission. The existing citation tests exercise automatic quote checks;
they do not establish clinical relevance or safety.

## Performance and reproducibility

The benchmark selects exactly 1,000 CSV rows with seed 4310. The timer starts before the
real authenticated CSV import request and ends after persisted classification, sentence
embedding, UMAP/HDBSCAN grouping, ranking and keyword naming. It includes real Presidio
and spaCy de-identification. No pipeline stage is replaced with a test double.

Model setup/download, baseline training and account creation are outside that timer.
The model cache is warm because the full dataset evaluation runs first. A label failure
or missing prediction makes the completion requirement fail rather than producing a
passing time. This measures the local baseline configuration, not hosted LLM throughput.

The API benchmark calls actual FastAPI routes with authentication and populated SQLite
data. It includes issues, comments, all three comparisons, suggestions, issue detail and
CSV export. Each endpoint has ten samples including its first request; the report records
all timings, p50, p95, maximum and HTTP success. The threshold is applied to the maximum.
The suggestions list is empty unless suggestions were generated. No browser rendering,
HTTP network travel, concurrent users or MySQL latency is measured. The result establishes
an in-process API timing only, not the entire dashboard page-load NFR.

The JSON report records Python, OS, architecture, CPU count, memory, every installed
package version, thread settings, data hash, code commit, dirty-tree flag, model and
prompt versions, batch size, worker count and grouping parameters. The sentence model's
snapshot revision and file hashes are recorded after loading. The lock file freezes the
installed transitive dependencies; the existing pyproject already pins direct dependencies
and the spaCy model wheel. Hosted models can still change server-side, and hardware and
dependency changes can alter clustering or timing. Re-run on a second member's machine
before claiming NFR5's independent reproduction check.

A larger minimum issue size can be explored without changing teammate-owned code:

```sh
bash scripts/evaluate.sh --min-cluster-size 40 --skip-benchmark --out work/grouping-40
```

Treat such parameter exploration as diagnostic. Keep the default result and disclose
changes; do not replace a failed default score with a tuned score without explanation.

## Responsibility check

| P3 Table 8 responsibility | Deliverable | Remaining external work |
|---|---|---|
| Synthetic data | 2,300-row import, separate truth, seeded generator, manifest and realism audit | Human realism review |
| Evaluation scripts | Existing scorers composed into JSON/Markdown reporting; public sentiment; annotation, agreement, issue and suggestion workflows | Human labelling and two-rater reviews; provider credentials for LLM comparisons |
| Testing | Data integrity, leakage, missing predictions, rubric validation, real import/classification/comparison tests; existing suite | Browser/user study remains with its owner |
| NFR3 | Actual 1,000-row pipeline and populated API measurements | Hosted LLM, MySQL, network and browser measurements |
| NFR5 | Seeds, dependency lock, model hashes, saved configs and one rerun command | Second member's independent rerun |

Quality-target failures in the measured report are findings for the owning members. They
are not hidden by the passing integration tests.

## Recorded quality audit

The [100-row audit](../reports/bhavya/quality-audit-100.csv) contains 25 randomly selected
comments from each original source, using seed 4310. All 100 were read in the AI review,
and changed rows were read again after correction. This is an AI qualitative review,
not a clinician review or one of the required human labelling exercises.

The review found family comments written as the patient, staff comments with
patient-perspective endings, unrelated follow-on questions in neutral reports, and the
unfamiliar abbreviation TTOs. The versioned wording pass corrects 721 rows across the
dataset, including 35 of the sampled rows. Dates, units, sources, issue assignments,
sentiment intent, trend and train/test splits are unchanged. No identifiable stories or
clinical advice were introduced.

The sample has 100 distinct texts and 34 comments of at most 15 words. It includes short
fragments, conventional sentences, several-sentence descriptions, lower-case openings,
informal expressions and occasional typos. Repeated phrasing remains: one five-word
opening occurs four times in the 100-row sample. This is acceptable as a reproducible
prototype fixture but does not justify a claim of human-equivalent language diversity.
No numerical human-realism score is claimed.

To reproduce the sample selection from the existing CSV without regenerating anything:

```sh
.venv/bin/python -m kaizen.evaluation.quality --out work/quality-review
```

That command writes a blank reviewer sheet and automated repetition statistics. It does
not fabricate review decisions. The submitted audit retains the actual before/after
review notes separately.

## Final measured findings

The final default run uses dataset version 2 and the existing minimum cluster size of 8.
The saved reports identify the code revision and exact dataset hash.

| Check | Measured result | Target / result |
|---|---:|---|
| De-identification recall, 150 comments / 300 fake details | 98.33% | At least 95%, PASS |
| ID, phone and email recall | 100% in each required type | 100%, PASS |
| Over-removal; unit removals | 0%; 0 | Under 5%; none, PASS |
| Synthetic sentiment macro F1, 734 held-out rows | 0.7241 | 0.75, FAIL |
| Synthetic category micro F1 | 0.8220 | 0.70, PASS |
| Synthetic stage accuracy | 74.11% | 65%, PASS |
| Synthetic high-urgency recall | 0% | 80%, FAIL |
| Public FFT sentiment macro F1, 1,388 labelled rows | 0.1299 | 0.75, FAIL |
| Planted recovery, default minimum size 8 | 0 of 8 | At least 6, FAIL |
| Planted recovery, exploratory minimum size 40 | 8 of 8 | At least 6, PASS for this configuration |
| Real baseline processing, 1,000 comments | 12.022 seconds | At most 900 seconds, PASS for measured scope |
| Slowest of the populated dashboard API samples | 0.021011 seconds | At most 2 seconds, PASS for in-process scope |

The [size-40 diagnostic](../reports/bhavya/grouping-40.json) isolates a grouping parameter
without changing teammate-owned code. The default produced 121 small issues; minimum
size 40 produced eleven larger ones and recovered all eight planted problems. Medication
had 86 patient/family and 20 staff comments in its recovered cluster. The recovered noise
issue had 186 patient/family and 18 staff comments: staff contamination makes the expected
patient-only pattern FAIL despite recovering the planted topic. Transport had 94
patient/family and 70 staff comments and was flagged rising. The adjusted Rand index
on planted comments changed from 0.1004 to 0.8156. That index is a diagnostic, not P3's human
issue-quality score. Independent API aggregation checks passed for all three groupings.

The size-40 run was chosen after seeing default fragmentation. It is explicitly
exploratory, not an untouched-test estimate or a replacement for the default failure.
The code default remains 8. Its timing is not used as the NFR3 benchmark; only the default
configuration was benchmarked. A separate [eleven-issue reviewer sheet](../reports/bhavya/issues-to-rate-grouping-40.csv)
is provided, but it has no completed human ratings.
