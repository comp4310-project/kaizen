# Notes for coding agents

Student group project, COMP 4310 at Lakehead. Five people, one term. Read this before
changing anything.

## State

The build has started, following P3 (`docs/p3-requirements-design.md`). Import,
de-identification and labelling are on `main`. Each part has an owner in P3 Table 8, so
check with them before changing their area.

## Layout

```
backend/                    Python package `kaizen`, tests and scripts
backend/kaizen/deid/        de-identification (FR2), the only code that sees original text
backend/kaizen/ingest/      CSV and form checks, then de-identify and save (FR1)
backend/kaizen/api/         FastAPI app, login and roles (NFR1)
backend/kaizen/classify/    labels each saved comment with an LLM through LiteLLM, plus a scikit-learn baseline (FR3)
backend/kaizen/issues/      groups labelled comments into named, ranked issues (FR4)
backend/kaizen/suggest/     documents, passage search and the citation check behind suggestions (FR7, NFR2)
backend/kaizen/db.py        database tables, see docs/data-model.md
docs/                       P0 to P3 deliverables, feedback, decisions
docs/meetings/              meeting notes
scripts/check_repo.py       hygiene checks, also runs in CI
.github/workflows/ci.yml    CI
```

Back end tests: `cd backend`, `pip install -e ".[dev]"`, then `pytest`. Never pass
original comment text to anything except `kaizen.deid.deidentify`, and never store or log
it.

## Rules

Never commit real patient data, `.env` files, API keys, or files over 5MB. Synthetic,
public, or de-identified data only. This is a course requirement, not a preference.

The repo is public. No student IDs and no personal email addresses anywhere in it, in any
file. Those belong in the D2L submission. `scripts/check_repo.py` fails on any 7-digit
number in a text file for this reason.

`main` is protected. Work on a branch, open a PR, one approval, squash merge.

Commit subjects are `area: what you did`, lower case, short. Explain why in the body when
the diff doesn't make it obvious. Don't write a paragraph for a one-line change.

Run `python scripts/check_repo.py` before pushing.

## Writing

Everything in this repo is read by markers and eventually by employers, so it has to read
like a person wrote it.

No em dashes. No "it's not just X, it's Y". No emoji in headings. No bolded lead-ins on
every bullet. Don't add a summary paragraph restating what was said. Don't use
`comprehensive`, `robust`, `seamless`, `leverage`, `delve`, `showcase`, or `streamline`.

Prefer plain prose over bullets, and specifics over adjectives. "Retries three times then
gives up" beats "robust error handling". If a section has nothing concrete in it, delete
it rather than padding it.

Say when something is broken or undecided instead of hedging around it.

## Don't add

Code of conduct, security policy, changelog, badge rows, issue templates, architecture
decision records. Five people don't need governance files, and an empty one is worse than
none. Don't create placeholder directories.
