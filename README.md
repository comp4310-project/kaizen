# Kaizen

Group project for COMP 4310 (Web Health Informatics), Lakehead University.

**Status: build starting.** P0 to P2 are submitted and P3 (requirements and design) is in
draft. Import, de-identification and labelling are on `main`; issue grouping is in
review. The plan is in [docs/p3-requirements-design.md](docs/p3-requirements-design.md).

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

Back end first. You need Python 3.12 or later. The install pulls the spaCy
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

To rerun the whole evaluation (NFR5) in one command, with no API key:

```
python -m kaizen.evaluate eval-results
```

It scores de-identification, trains the TF-IDF baseline on the synthetic training split and
scores it on the 300 held-out comments, imports the synthetic CSV into a fresh SQLite database
in `eval-results/`, builds issues from the template labels and counts how many of the 8
built-in problems it finds, checks the staff-only, patient-only and rising problems (FR4, FR5),
and times 1,000 comments (NFR3). It writes `results.md` and `results.json` with every number
next to its P3 target, plus library versions, seeds and the git commit. It takes a few minutes,
most of it de-identification and the sentence model. Add `--llm anthropic/claude-haiku-5-5`
to also score an LLM labeller on the held-out split; that one needs the API key and costs money.

The synthetic data is in `tests/data/synthetic*` and comes from
`python scripts/make_synthetic.py` (seed 4310). Rerunning it gives the same files byte for byte,
and a test fails if the committed files go stale.

To run the API locally (SQLite by default, set `KAIZEN_DATABASE_URL` for MySQL), create
an admin account and start the server, then open http://localhost:8000/docs:

```
python -m kaizen.cli create-user admin --role admin
uvicorn kaizen.api.app:create_app --factory --reload
```

The tables and endpoints are described in [docs/data-model.md](docs/data-model.md).

The front end is a React and TypeScript app in `frontend/` with login, the ranked issues
table, an issue's comments, and suggestion review. With the API running on port 8000, run
`npm install` and `npm run dev` in `frontend/` and open http://localhost:5173. Details and
the pages still to build are in [frontend/README.md](frontend/README.md).

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
| P3 Requirements and Design | Draft | [docs/p3-requirements-design.md](docs/p3-requirements-design.md) |

Instructor feedback on each one, and what we changed because of it, is in
[docs/feedback.md](docs/feedback.md).

## Working on this

See [CONTRIBUTING.md](CONTRIBUTING.md). Branch, open a PR, get one review, squash merge.
`main` is protected so nobody can push to it directly.

## License

[MIT](LICENSE)
