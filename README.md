# Kaizen

Group project for COMP 4310 (Web Health Informatics), Lakehead University.

**Status: build starting.** P0 to P2 are submitted and P3 (requirements and design) is in
draft. De-identification is the first piece of code. The plan is in
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

## Stack

From P3: Python 3.12 and FastAPI for the back end, React with TypeScript for the front end,
MySQL, Presidio and spaCy for de-identification, BERTopic for grouping comments, an LLM
through LiteLLM, and Chroma for the documents behind suggestions. See P3 section 4 for why.

## Running it

Only the back end tests so far. You need Python 3.12 or later. The install pulls the spaCy
English model, which is about 400MB.

```
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; on macOS or Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

To see the de-identification score and every miss on the test set:

```
python -m kaizen.deid.evaluate tests/data/deid_test_set.jsonl
```

To run the API locally (SQLite by default, set `KAIZEN_DATABASE_URL` for MySQL), create
an admin account and start the server, then open http://localhost:8000/docs:

```
python -m kaizen.cli create-user admin --role admin
uvicorn kaizen.api.app:create_app --factory --reload
```

The tables and endpoints are described in [docs/data-model.md](docs/data-model.md).

## Data

Synthetic, public, or properly de-identified data only. No real patient information at any
point, which is a course requirement and also just sensible. Don't commit `.env` files or
API keys either.

This repo is public, so no student IDs and no personal email addresses anywhere in it.
Those go in the D2L submission, not here.

## Deliverables

| Deliverable | Status | Document |
|---|---|---|
| P0 Team Formation and Topic Selection | Submitted | [docs/p0-team-formation.md](docs/p0-team-formation.md) |
| P1 Project Proposal | Submitted, 94/100 | [docs/p1-proposal.md](docs/p1-proposal.md) |
| P2 Literature and Existing-System Analysis | Submitted, 96/100 | [docs/p2-literature-review.md](docs/p2-literature-review.md) |
| P3 Requirements and Design | Draft | [docs/p3-requirements-design.md](docs/p3-requirements-design.md) |

Instructor feedback on each one, and what we changed because of it, is in
[docs/feedback.md](docs/feedback.md).

## Working on this

See [CONTRIBUTING.md](CONTRIBUTING.md). Branch, open a PR, get one review, squash merge.
`main` is protected so nobody can push to it directly.

## License

[MIT](LICENSE)
