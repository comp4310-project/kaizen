# Data model and API

Week 1 deliverable from P3 Table 7. This covers import, de-identification, accounts and
the log (FR1, FR2, NFR1). Labels, issues and suggestions are listed at the end for their
owners to fill in. Everything here is a draft until the team agrees it.

## CSV upload

One row per comment, with a header row. Columns can be in any order and extra columns
are ignored.

| Column | Values |
|---|---|
| `text` | The comment, up to 5,000 characters |
| `source` | `patient`, `family`, `staff`, `nurse` or `physician`. Stored as `patient_family` or `staff` |
| `unit` | A code from the unit list below |
| `date` | `YYYY-MM-DD`, not in the future |

A row that breaks any of these is skipped and reported with its line number and the
reason. The reason never includes the comment. A file with a missing column, more than
20,000 rows, over 5MB or not in UTF-8 is rejected as a whole.

## Unit list

Draft, in `backend/kaizen/units.py`: ED, ICU, 2A, 3A, 4A, 4B, 5A, 6A. Unit names and codes
are never removed by de-identification.

## Tables

| Table | Holds | Notes |
|---|---|---|
| `users` | username, bcrypt hash, role (`qi`, `manager`, `admin`), unit | A manager must have a unit |
| `auth_tokens` | SHA-256 of each login token, user, expiry | Tokens last 12 hours |
| `import_batches` | channel (`csv` or `form`), who uploaded, rows saved and rejected | The file name is not kept, since it can hold a name |
| `comments` | source, unit, date, de-identified text, count of each tag removed | Original text is never written |
| `activity_log` | who, action, what it was about, details, when | Details never hold comment text |

Logged actions so far: `login`, `login_failed`, `import_csv`, `submit_form`,
`view_comments`, `create_user`.

## API

Run with `uvicorn kaizen.api.app:create_app --factory --reload` from `backend/`. FastAPI
serves the full, current docs at `/docs`.

| Method and path | Who | Does |
|---|---|---|
| `POST /auth/login` | anyone | Returns a token to send as `Authorization: Bearer <token>` |
| `GET /me` | logged in | The current user's name, role and unit |
| `GET /units` | anyone | The unit list, for the form |
| `POST /feedback` | anyone, no login | The web form: `text`, `source`, `unit`, optional `date` |
| `POST /imports` | QI, admin | CSV upload as a `file` field; returns counts and row errors |
| `GET /comments` | QI, admin, manager | De-identified comments, filter by `unit` and `source`. Managers only get their own unit |
| `POST /users` | admin | Create an account |
| `GET /issues` | QI, admin, manager | The newest run's ranked issues. Managers only get issues with comments from their unit, with `unit_size` set |
| `GET /issues/{id}/comments` | QI, admin, manager | The comments behind an issue with their labels, most typical first. Managers only get their unit's comments, and 404 for issues outside it |

Create the first admin with `python -m kaizen.cli create-user admin --role admin`.

## Labels (FR3)

One `comment_labels` row per comment, written by `python -m kaizen.classify label`. The
values are the strings in `docs/labelling-guide.md`.

| Column | Holds |
|---|---|
| `sentiment`, `stage`, `urgency` | One value each |
| `categories` | A JSON list of HCAT categories, possibly empty |
| `status` | `suggested` until a person checks it, then `confirmed` (FR6) |
| `suggested` | What the model first said, kept after corrections so we can still score the model |
| `labeller`, `prompt_version` | Model and effort (for example `anthropic/claude-haiku-5-5/low`) and a hash of the prompt (NFR5) |
| `confirmed_by`, `confirmed_at` | Who checked it and when |

Comments without a row are the ones still to label, so a rerun only sends those. Each run
adds a `label_comments` row to the activity log with counts only.

## Issues (FR4)

`python -m kaizen.issues build` groups the labelled negative and neutral comments into
issues. Praise and unlabelled comments are left out. Every run is kept in `issue_runs`
(model, settings, how many comments and outliers) and the dashboard should show the newest.

| Table | Holds |
|---|---|
| `issues` | run, rank (1 is most pressing), name, keywords, size, negative and high-urgency shares, patient and staff counts, main stage, top 3 categories, comments in the last 7 days, rising flag, score |
| `issue_comments` | issue and comment ids; `typical` marks the 10 comments closest to the issue's centre, which are the ones sent to the LLM for the name |

Score is comments x (0.5 + negative share) x (1 + high-urgency share). An issue is rising when
its last 7 days hold at least 3 comments and at least twice its weekly average over the 4
weeks before. The patient and staff counts are there for the comparison view (FR5).

## Suggestions (FR7)

`kaizen.suggest.draft` writes up to three `suggestions` rows for an issue. The model gets the
issue's name, keywords and stage and the five closest document passages, never comment text.
Any suggestion with a quote that is not word for word in its passage is dropped before it is
saved (NFR2).

| Column | Holds |
|---|---|
| `issue_id` | The issue row it was drafted for. Issue ids change on every `issues build`, so the next four columns keep a copy |
| `issue_name`, `issue_keywords`, `issue_comment_ids` | The issue as it was when the suggestion was drafted |
| `change`, `owner`, `stage`, `measure` | The parts P3 requires of an actionable suggestion |
| `citations` | A JSON list of passage id, document id, title, section heading and quote |
| `status` | `suggested` until a person accepts, edits or rejects it |
| `drafted` | What the model first wrote, kept after edits so suggestions can still be scored |
| `model`, `prompt_version` | Model and effort, and a hash of the prompt (NFR5) |
| `created_by`, `decided_by`, `decided_at` | Who asked for it, and who decided and when |

Each draft adds a `draft_suggestions` row to the activity log with how many were kept and
dropped and why, but no suggestion text.

The documents are Markdown files in `KAIZEN_CORPUS_DIR` (default `documents`), in the format
described in `kaizen/suggest/corpus.py`. `python -m kaizen.suggest index` checks them and
caches the passage vectors in `kaizen-passages.npz`; `python -m kaizen.suggest draft <issue id>`
drafts from the command line.

| Endpoint | Who | What |
|---|---|---|
| `POST /issues/{id}/suggestions` | QI, admin | Drafts and saves suggestions for an issue. 503 if no documents are loaded, 502 if the model gives no usable reply |
| `GET /issues/{id}/suggestions` | QI, admin | Suggestions drafted for that issue row, newest first |
| `GET /suggestions` | QI, admin | Review queue, filter with `status=suggested` |
| `POST /suggestions/{id}/decision` | QI, admin | `{"decision": "accept"}`, `"reject"`, or `"edit"` with any of `change`, `owner`, `stage`, `measure` |

Managers can't see suggestions; FR7 is for QI staff. Every decision adds a
`decide_suggestion` row to the activity log with the decision and the names of edited fields,
never the text.

## Still to add

These belong to other members (P3 Table 8). The comment `id` is the key to join on.

- Label corrections and merges should each add an `activity_log` row.
