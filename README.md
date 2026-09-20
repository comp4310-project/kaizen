# Kaizen

Group project for COMP 4310 (Web Health Informatics), Lakehead University.

**Status: placeholder.** Topic and stack aren't final and still need approval from the
instructor. The repo exists so we can start working properly.

## The idea

Hospitals collect a lot of written feedback from patients, doctors, nurses and visitors,
and most of it never gets read properly. The same problem can show up in fifty comments
across three wards and nobody notices.

We want to build something that groups feedback into recurring problems, shows where in
the hospital's workflow they're happening, and suggests fixes based on hospital policy
and published research.

Named after *kaizen* (改善), continuous improvement from lots of small changes. It's a
term that actually gets used in hospital operations.

## Team

| Name | Email | GitHub |
|------|-------|--------|
| Mohammed Asrar Ali | TBD | [@Asrar-ali](https://github.com/Asrar-ali) |
| TBD | TBD | [@Muazhuja01](https://github.com/Muazhuja01) |
| TBD | TBD | TBD |
| TBD | TBD | TBD |

## Stack

Nothing decided yet. Currently thinking React + TypeScript on the front, Python/FastAPI
and Postgres on the back, and an LLM API with embeddings for the clustering and
suggestions.

## Deliverables

P0 draft is in [docs/p0-team-formation.md](docs/p0-team-formation.md). Nothing else started.

## Working on this

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: branch, open a PR, get one review,
squash merge. `main` is protected so nobody can push to it directly.

Synthetic or public data only — the course rules don't allow real patient data, and we
shouldn't commit `.env` files or API keys either.

## License

[MIT](LICENSE)
