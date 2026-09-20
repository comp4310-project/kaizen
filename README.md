# Kaizen

Group project for COMP 4310 (Web Health Informatics), Lakehead University.

**Status: placeholder.** The topic below still needs approval from the instructor, and the
stack isn't decided. There's no code yet.

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

| Name | Email | GitHub |
|------|-------|--------|
| Mohammed Asrar Ali | TBD | [@Asrar-ali](https://github.com/Asrar-ali) |
| TBD | TBD | [@Muazhuja01](https://github.com/Muazhuja01) |
| TBD | TBD | TBD |
| TBD | TBD | TBD |

## Stack

Undecided. Currently leaning towards React and TypeScript on the front, Python with
FastAPI and Postgres on the back, and an LLM API with embeddings for the clustering and
the suggestions. This will change.

## Running it

Nothing to run yet. Setup instructions go here once there's code.

## Data

Synthetic, public, or properly de-identified data only. No real patient information at any
point, which is a course requirement and also just sensible. Don't commit `.env` files or
API keys either.

## Deliverables

P0 draft: [docs/p0-team-formation.md](docs/p0-team-formation.md). Nothing else started.

## Working on this

See [CONTRIBUTING.md](CONTRIBUTING.md). Branch, open a PR, get one review, squash merge.
`main` is protected so nobody can push to it directly.

## License

[MIT](LICENSE)
