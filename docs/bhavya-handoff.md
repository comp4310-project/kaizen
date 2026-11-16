# Bhavya's submission handoff

PR [#32](https://github.com/comp4310-project/kaizen/pull/32) delivered the implementation
and was merged as `a456745`. Its CI passed. This handoff checks P3 Tables 8 and 9 against
that main revision. No dataset generation, dependency installation or pipeline benchmark
was repeated for this documentation review.

## Responsibility checklist

| Responsibility | Delivered | Participation still required |
|---|---|---|
| Synthetic data | Complete: 2,300 unique fictional comments, separate truth and manifest, seeded generator and 100-row AI quality audit | Human realism review; AI review does not establish human realism |
| Evaluation scripts | Complete: existing scorers reused for de-identification, classification, issue recovery, comparison and suggestion-rating workflows; JSON and readable reports | People must supply genuine labels and ratings; credentials needed for LLM comparisons |
| Testing and integration | Complete: recorded 192 backend tests passed, zero failed; frontend build, package consistency and repository hygiene passed | Required peer review of future changes |
| NFR3 performance | Benchmark implementation and local measurements complete | Browser page-load, network, MySQL and hosted-LLM performance remain unmeasured |
| NFR5 reproducibility | Seeds, dependency lock, model hashes, parameters, commands and annotation guide complete | A second member must perform and document an independent rerun |

Failed quality targets below are measured findings, not missing evaluation code. Full
NFR3 deployment validation and NFR5 independent reproduction cannot be claimed complete.

## Dataset and evidence

The four-column import is [comments.csv](../data/synthetic/comments.csv): 1,500
patient/family and 800 staff comments, eight planted problems and 800 background comments.
Sources are 905 patient, 595 family, 496 nurse and 304 physician. Dates span September 21
to November 1, 2026; all eight permitted units occur. Internal transport increases across
six weeks: 8, 12, 18, 28, 42 and 72 comments.

[truth.jsonl](../data/synthetic/truth.jsonl) contains AI-authored intended labels and planted
metadata. These are synthetic intent labels, never human annotations. The audit sampled
25 comments per source and led to wording corrections in 721 rows, including 35 sampled
rows. Repeated narrative seeds remain a limitation. No real patient stories are claimed.

The implementation is in `backend/kaizen/evaluation/`, with focused tests in
`backend/tests/test_evaluation.py`, dependency pins in `backend/requirements-evaluation.lock`
and the wrapper in `scripts/evaluate.sh`. Full usage is in [Data and evaluation](data-evaluation.md).
The separate 1,200-row fixture and `kaizen.evaluate` runner are retained; their isolated
experiments must not be combined with this 2,300-row prediction-based experiment.

## Recorded results

These values come from [results.json](../reports/bhavya/results.json), measured on
revision `ace0d7b` before PR #32 was squash-merged. Configuration: baseline TF-IDF/logistic
regression, keyword names, seed 4310, batch size 50, one worker, minimum cluster size 8.
Package versions, environment and model-file hashes are in the report.

| P3 check | Recorded measurement | Interpretation |
|---|---|---|
| De-identification | 98.33% recall on 150 comments / 300 fake details; required ID/phone/email recall 100%; over-removal 0%; unit removals 0 | PASS against all de-identification targets |
| Synthetic sentiment | Macro F1 0.7241 | FAIL against 0.75 |
| Synthetic categories | Micro F1 0.8220; per-category scores saved | PASS against 0.70 |
| Synthetic stage | Accuracy 74.11% | PASS against 65% |
| Synthetic urgency | High-urgency recall 0% | FAIL against 80% |
| Public FFT sentiment | Macro F1 0.1299 on 1,388 labelled ambulance comments | FAIL against 0.75; 237 unlabeled rows excluded |
| Default issue recovery | 0/8 | FAIL against at least 6/8 |
| Exploratory minimum size 40 | 8/8 | PASS for that configuration; chosen after seeing fragmentation |
| Comparison integrity | Category, stage and unit counts match saved predictions | PASS for API aggregation |
| Processing 1,000 comments | 12.022436 seconds | PASS against 900 seconds for the measured scope |
| Dashboard APIs | Maximum sample 0.021011 seconds | PASS against 2 seconds for in-process API calls |

Classification figures use 734 held-out synthetic rows with different narrative seeds
from training, not the planned 300 human-labelled test rows. Public sentiment uses
published FFT labels and is reported separately; public HCAT labels are unavailable.

The [size-40 report](../reports/bhavya/grouping-40.json) preserves the default failure.
Medication has both source groups and transport is rising, but the recovered noise
cluster includes 18 staff comments, so the patient-only pattern fails. This diagnostic
has no completed human issue ratings and does not establish the 70% good-issue target.

Processing includes real import, de-identification, persisted classification, embedding,
grouping, ranking and keyword naming with SQLite. It excludes training, downloads and
account setup and uses a warm cache. API timing uses FastAPI TestClient; it does not
measure browser rendering, network travel, concurrent load or MySQL. Suggestions were
not generated for this benchmark.

[Test evidence](../reports/bhavya/verification.json) records 192 passing backend tests,
two dependency warnings, a passing frontend build and byte-for-byte in-memory dataset
reproduction. That reproduction check was performed by AI in this workspace; no second
person's reproduction is recorded.

## Commands for the next member

From the repository root, with the existing environment, rerun everything with:

```sh
bash scripts/evaluate.sh --with-public --out work/reproduction
```

This regenerates the fixture, downloads the pinned public extract, evaluates, benchmarks,
runs tests and checks hygiene. `--with-public` must be the first argument. Omitting it
runs the synthetic workflow. `--out` preserves the submitted reports. Future runs need
network access if package/model/public-data caches are unavailable. For a fresh Python
3.12 environment on Linux or WSL, follow the installation commands in the full guide.

To regenerate only the synthetic fixture:

```sh
.venv/bin/python -m kaizen.evaluation.generate
```

A zero exit status is insufficient evidence that every target passed: quality failures
are saved as FAIL, and caught grouping errors are saved as NOT_MEASURED. Read both
`results.json` and `summary.md`. This review ran neither command above.

## Human review queue

1. Two members independently label copies of `reports/bhavya/calibration-100.csv`, check
   agreement against kappa 0.6 and refine the guide. Adjudicate the separate
   `heldout-300.csv` without training or prompt tuning on it. Use the documented
   `kaizen.evaluation.score agreement` and `labels` commands. Blank sheets and synthetic
   intent are not completed gold labels.
2. Two reviewers rate ten comments from each top-15 issue using `issues-to-rate.csv`.
   Score with `kaizen.evaluation.score issues`. The size-40 sheet contains only eleven
   issues and must be described as partial against the top-15 protocol.
3. Generate the required suggestions and no-document controls when credentials are
   available, then have two people score 40 suggestions for relevance, actionability,
   citation support and unsafe treatment advice. Use the existing suggestion collector
   and `kaizen.evaluation.score suggestions`. No human suggestion score is recorded.
4. Have a second member run the reproduction command and record revision, environment,
   result differences and their actual participation. Do not label the existing AI
   in-memory check as independent reproduction.
5. Coordinate deployed performance and the five-person SUS/accessibility study with the
   responsible teammates. Browser/SUS results cannot be inferred from API timings or builds.
