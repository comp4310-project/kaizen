# Kaizen

Group project for COMP 4310 (Web Health Informatics), Lakehead University.

**Status: working prototype (P4).** Every Must and Should requirement from P3 runs end to
end: upload, de-identification, labelling, issue grouping, the patient vs staff comparison,
corrections, the dashboard and cited suggestions. First results against P3 Table 9, including
the targets we missed, are in [docs/evaluation](docs/evaluation/README.md) and
[docs/data-evaluation.md](docs/data-evaluation.md). The plan is in
[docs/p3-requirements-design.md](docs/p3-requirements-design.md).

## The idea

Hospitals collect a lot of written feedback from patients, doctors, nurses and visitors.
Most of it gets counted and filed, so a problem that keeps recurring across different
wards, described in slightly different words each time, never gets spotted as one problem.

We want to build something that groups feedback into recurring issues, works out where in
the hospital's workflow each one is happening, and suggests fixes based on hospital policy
and published research on quality improvement.

Named after kaizen (改善), continuous improvement from lots of small changes. It's a term
that actually gets used in hospital operations, which is why we picked it.

## Team

| Name | GitHub |
|------|--------|
| Hemanth Reddy Basireddy | [@HemanthReddy1518](https://github.com/HemanthReddy1518) |
| Hujaifa Muaz | [@Muazhuja01](https://github.com/Muazhuja01) |
| Mohammed Asrar Ali | [@Asrar-ali](https://github.com/Asrar-ali) |
| Aansh Amitabh Arora | [@AanshXArora](https://github.com/AanshXArora) |
| Bhavya Bhatt | [@Bhavya1435](https://github.com/Bhavya1435) |

## What works

| Requirement | What you can do | Code |
|---|---|---|
| FR1 | QI staff and admins can upload feedback and see which rows were skipped. Anyone can send one comment without logging in. | Upload CSV (`/imports`) and Send feedback (`/feedback`) |
| FR2 | Names, dates, phones, emails, health card and record numbers are replaced with tags before anything is saved | `backend/kaizen/deid/` |
| FR3 | Each comment gets a sentiment, HCAT categories, a stage of care and a suggested urgency | `backend/kaizen/classify/` |
| FR4 | Similar comments are grouped into named issues, ranked, with a rising flag | `backend/kaizen/issues/` |
| FR5 | Patient or family vs staff counts by category, stage or unit | `/compare`, Compare page |
| FR6 | Confirm or correct labels, redact a missed detail, rename or merge issues; all logged | issue page |
| FR7 | Two or three suggestions per issue that cite our documents, to accept, edit or reject | `backend/kaizen/suggest/` |
| FR8 | Ranked issues, their comments, unit and source filters, CSV export | `frontend/` |

Trend charts and the improvement tracker are still open (both Could in P3).

## Stack

Python 3.12 and FastAPI, SQLAlchemy with SQLite (MySQL through `KAIZEN_DATABASE_URL`), React
19 and TypeScript with Vite, Presidio and spaCy for de-identification, and LLM calls through
LiteLLM. Three changes from P3, each explained in [docs/decisions.md](docs/decisions.md):
issue grouping runs BERTopic's steps (sentence embeddings, UMAP, HDBSCAN, class-based TF-IDF)
without the BERTopic package and its PyTorch download, passage search uses numpy instead of
Chroma, and with no API budget the LLM steps run on a free local model for now.

## Quick demo

One command builds a database by running the real pipeline on the 2,300 synthetic comments,
then starts the app. No API key and no cost. You need Python 3.12 or newer and Node 20.19 or
newer (we use 24). From the repository root on Windows:

```
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

and on macOS or Linux:

```
bash scripts/demo.sh
```

The script checks Python, Node and npm, creates `backend/.venv` and installs the back end,
runs `npm ci`, and builds `work/demo.db`. Each of those is skipped when it is already done
and `pyproject.toml` or `package-lock.json` has not changed. It then starts the API and the
front end with their logs in `work/logs/`, opens http://localhost:5173 and prints the
accounts. Ctrl+C stops both. On a Windows laptop the first run took about six minutes, four
and a half of them the back end install, and later runs were up in 15 seconds.

The first run asks for one password for three accounts: `demo-qi` (QI staff), `demo-manager`
(unit 4B only) and `demo-admin`. It is not printed or saved anywhere; if you forget it, run
again with `-Fresh` (`--fresh` in bash) to rebuild the database with a new one. If Ollama is
running with `qwen2.5:7b`, suggestions use it. If `ANTHROPIC_API_KEY` is set, they use the
hosted models instead, unless you pass `-Local`. Other options are `-Check` (checks only,
changes nothing), `-ApiPort` and `-WebPort`; `Get-Help scripts\demo.ps1 -Detailed` or
`bash scripts/demo.sh --help` lists them all.

### Before the demo

1. `git checkout main` and `git pull`.
2. Run the script with `-Check` (`--check` in bash). Every line should say `ok`; a `FAIL`
   line comes with the fix.
3. Start Ollama (the app, or `ollama serve`) and run `ollama pull qwen2.5:7b` if `-Check`
   says the model is missing. Without it everything except suggestions still works.
4. Run the script for real once, log in as `demo-qi` with your password, open an issue and
   draft suggestions. The first draft also loads the documents and embeds them (14 seconds
   with Ollama on our test laptop), so get that out of the way before people are watching.

### The same steps by hand

```
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; on macOS or Linux: source .venv/bin/activate
pip install -e ".[dev]"
python scripts/demo_data.py ../work/demo.db
```

The script asks for the password for the three accounts. It imports the comments through
the CSV checks and de-identification, labels them with the TF-IDF baseline, and builds the
ranked issues, which takes about two minutes. Then start the API on that database:

```
# PowerShell: $env:KAIZEN_DATABASE_URL = "sqlite:///../work/demo.db"
export KAIZEN_DATABASE_URL=sqlite:///../work/demo.db
uvicorn kaizen.api.app:create_app --factory
```

and in a second terminal:

```
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 and log in as `demo-qi` to try **Upload CSV**. To try the
public feedback form, follow **Send feedback without logging in** on the login page.
New feedback is saved for the next labelling and issue grouping run. The API docs are
at http://localhost:8000/docs. If the API runs on another port, set `KAIZEN_API_PORT` to
it before `npm run dev` so the front end's `/api` proxy follows.

## Running it yourself

After the install above, `pytest` in `backend/` runs the 194 back end tests. On a fresh
database, create the first account with
`python -m kaizen.cli create-user admin --role admin`, upload a CSV with `POST /imports`
(the API docs page has a form for it), then run each step:

```
python -m kaizen.classify label          # label new comments (FR3)
python -m kaizen.issues build            # group labelled comments into issues (FR4)
python -m kaizen.suggest index           # embed the documents behind suggestions (FR7)
python -m kaizen.suggest draft ISSUE_ID  # draft suggestions for one issue
```

The CSV format and every table and endpoint are in [docs/data-model.md](docs/data-model.md).

### Settings

All optional, set as environment variables. Never put keys in the repository.

| Variable | Default | What it does |
|---|---|---|
| `KAIZEN_DATABASE_URL` | local SQLite file | for example `mysql+pymysql://user:pass@localhost/kaizen` |
| `KAIZEN_LABEL_MODEL`, `KAIZEN_LABEL_EFFORT` | `anthropic/claude-haiku-5-5`, `low` | model for labelling |
| `KAIZEN_NAME_MODEL` | `anthropic/claude-haiku-5-5` | model for issue names (`--keyword-names` skips it) |
| `KAIZEN_SUGGEST_MODEL`, `KAIZEN_SUGGEST_EFFORT` | `anthropic/claude-opus-5-5`, `medium` | model for suggestions |
| `ANTHROPIC_API_KEY` | none | needed only for the `anthropic/...` models |
| `KAIZEN_CORPUS_DIR` | `documents` | documents behind suggestions |
| `KAIZEN_EMBED_CACHE` | system cache | where the 90MB sentence model is stored |

Model names go through LiteLLM, so a free local model works without code changes. With
[Ollama](https://ollama.com) running, set `KAIZEN_LABEL_MODEL`, `KAIZEN_NAME_MODEL` and
`KAIZEN_SUGGEST_MODEL` to `ollama/qwen2.5:7b`. That is what our P4 LLM results used.

## Evaluation

Both runners need no API key.

- `python -m kaizen.evaluate eval-results` (from `backend/`) scores de-identification, the
  baseline on the 300 held-out comments of the 1,200-comment set in `tests/data/`, issue
  finding and the FR5 patterns, and timing. It writes `results.md` and `results.json`.
- `bash scripts/evaluate.sh --with-public` (from the repository root) runs Bhavya's
  2,300-comment set in `data/synthetic/` and the public NHS comments end to end. See
  [docs/data-evaluation.md](docs/data-evaluation.md).

Results are in [docs/evaluation](docs/evaluation/README.md),
[reports/bhavya](reports/bhavya/summary.md) and
[reports/issue-size-default](reports/issue-size-default/summary.md). Synthetic, public and
simulated-rater results are always reported separately.

## Data

Synthetic, public, or properly de-identified data only. No real patient information at any
point, which is a course requirement and also just sensible. Don't commit `.env` files or
API keys either.

This repo is public, so no student IDs and no personal email addresses anywhere in it.
Those go in the D2L submission, not here.

Public data we use, fetched by script rather than committed:

- `backend/scripts/fetch_fft_comments.py` downloads 1,625 real NHS Friends and Family Test
  comments (North East Ambulance Service, "See and Convey") from NHS England's
  [pxtextmining](https://github.com/The-Strategy-Unit/pxtextmining) and converts them to our
  CSV upload format in `data/raw/`, which is gitignored. They are ambulance comments, not ward
  comments, and they go through de-identification on upload like any other file.
- `documents/ontario-excellent-care-for-all-act.md` is sections 2 to 8 of Ontario's
  Excellent Care for All Act, 2010, reproduced under the King's Printer's terms for statutes.

## Deliverables

| Deliverable | Status | Document |
|---|---|---|
| P0 Team Formation and Topic Selection | Submitted | [docs/p0-team-formation.md](docs/p0-team-formation.md) |
| P1 Project Proposal | Submitted, 94/100 | [docs/p1-proposal.md](docs/p1-proposal.md) |
| P2 Literature and Existing-System Analysis | Submitted, 96/100 | [docs/p2-literature-review.md](docs/p2-literature-review.md) |
| P3 Requirements and Design | Submitted | [docs/p3-requirements-design.md](docs/p3-requirements-design.md) |
| P4 Prototype and Progress Evaluation | In progress | report on D2L; results in [docs/evaluation](docs/evaluation/README.md) |

Instructor feedback on each one, and what we changed because of it, is in
[docs/feedback.md](docs/feedback.md).

## Working on this

See [CONTRIBUTING.md](CONTRIBUTING.md). Branch, open a PR, get one review, squash merge.
`main` is protected so nobody can push to it directly.

## License

[MIT](LICENSE)
