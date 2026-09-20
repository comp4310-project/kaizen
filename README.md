# Kaizen

> **Status: placeholder.** The team, project topic, and technology stack on this page are
> preliminary and pending instructor/TA approval (see [P0](docs/p0-team-formation.md)).
> Nothing here is final. Structure exists so that collaboration starts on day one.

Turning hospital feedback into actionable quality improvements.

**COMP 4310 — Web Health Informatics**
Department of Computer Science, Lakehead University, Thunder Bay, ON

---

## Problem

Hospitals collect large volumes of free-text feedback from patients, families, nurses,
physicians, and visitors. Most of it is read once, counted, and filed. Recurring problems
stay invisible because nobody can read ten thousand comments and notice that the same
handover failure appears in three different wards under four different descriptions.

## What we are building

A decision-support system that:

1. **Ingests** free-text feedback from multiple stakeholder groups.
2. **Clusters** it into recurring themes using NLP and large language models.
3. **Maps** each theme to the hospital workflow stage where it originates.
4. **Proposes** candidate interventions grounded in hospital policy and published
   quality-improvement literature.
5. **Estimates** the expected impact of each intervention.

Named for *kaizen* (改善) — continuous improvement driven by many small changes surfaced
by the people closest to the work. It is established Lean healthcare vocabulary, and it
describes the loop this system is meant to close.

## Intended users

Quality-improvement teams, unit managers, and hospital administrators.

## Scope and limitations

- **Synthetic, public, or appropriately de-identified data only.** No confidential patient
  information is used at any point.
- This is a course prototype. It is **not** a clinically validated medical device or
  diagnostic system.
- AI-generated output is **decision support**, not an authoritative clinical or
  administrative decision. Every generated suggestion is presented for human review.
- Evaluating whether generated output is faithful to its source data is part of the
  project, not an afterthought.

## Team

| Name | Lakehead email | GitHub | Role |
|------|----------------|--------|------|
| Mohammed Asrar Ali | _TBD_ | [@Asrar-ali](https://github.com/Asrar-ali) | _TBD_ |
| _TBD_ | _TBD_ | [@Muazhuja01](https://github.com/Muazhuja01) | _TBD_ |
| _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| _TBD_ | _TBD_ | _TBD_ | _TBD_ |

## Technology stack

Preliminary and subject to change. See [ADR directory](docs/decisions/) for decisions as
they are made and justified.

| Layer | Candidate |
|-------|-----------|
| Frontend | React + TypeScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Semantic search | Embeddings + vector store |
| NLP / GenAI | LLM API or locally hosted model |
| Clustering | scikit-learn / topic modelling |
| CI | GitHub Actions |

## Repository layout

```
docs/
  p0-team-formation.md   P0 deliverable
  decisions/             architecture decision records — what we chose and why
  meetings/              dated meeting notes
  research/              literature and existing-system review
.github/
  workflows/             CI
  ISSUE_TEMPLATE/        issue forms
```

## Course deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| P0 | Team formation and topic selection | In progress |
| P1 | Project proposal | Not started |
| P2 | _TBD_ | Not started |
| P3 | _TBD_ | Not started |
| P4 | _TBD_ | Not started |
| P5 | _TBD_ | Not started |

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before your first pull request. Short version:
branch, commit with a conventional prefix, open a PR, get one approval, squash merge.
`main` is protected — nobody pushes to it directly, including repository owners.

## License

[MIT](LICENSE)
