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

## Still to add

These belong to other members (P3 Table 8). The comment `id` is the key to join on.

- **Issues** (Muaz, FR4): issue name, which comments belong to it, rank.
- **Suggestions** (Asrar, FR7): issue, text, cited passage, and the accept, edit or reject
  decision with who made it.
- Label corrections, merges and suggestion decisions should each add an `activity_log` row.
