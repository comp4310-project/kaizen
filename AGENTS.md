# Notes for coding agents

Student group project, COMP 4310 at Lakehead. Five people, one term. Read this before
changing anything.

## State

No application code yet. The repo currently holds the P0 deliverable draft and the
collaboration setup. The topic is not approved yet, so don't scaffold an app.

## Layout

```
docs/p0-team-formation.md   P0 deliverable draft
docs/decisions.md           what we picked and why
docs/meetings/              meeting notes
scripts/check_repo.py       hygiene checks, also runs in CI
.github/workflows/ci.yml    CI
```

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
