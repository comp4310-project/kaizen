# Contributing

House rules for the Kaizen repository. They exist so that four people can work in parallel
without stepping on each other, and so that our history reads clearly when we submit it.

## Ground rules

- `main` is always in a working state. It is protected: no direct pushes, no exceptions.
- All work happens on a branch and lands through a pull request.
- Every pull request needs one approving review from someone other than the author.
- Do not merge your own pull request without an approval, even for a typo fix.

## Branches

```
<type>/<short-description>
```

| Type | Use for |
|------|---------|
| `feat/` | new functionality |
| `fix/` | bug fixes |
| `docs/` | documentation, deliverables, meeting notes |
| `research/` | literature review, experiments, spikes |
| `chore/` | tooling, CI, dependencies, housekeeping |
| `refactor/` | restructuring without behaviour change |

Examples: `feat/feedback-ingest-api`, `docs/p1-proposal`, `research/topic-modelling-comparison`

Use lowercase and hyphens. Keep it under about 40 characters.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/). Format:

```
<type>: <imperative summary under 72 characters>

Optional body explaining WHY, wrapped at 72 characters.
```

Types: `feat`, `fix`, `docs`, `research`, `chore`, `refactor`, `test`, `style`.

```
feat: add feedback clustering endpoint
docs: draft P1 proposal problem statement
fix: handle empty feedback batches in ingest
```

Write the body when the reason is not obvious from the diff. The diff shows what changed;
the message should explain why it changed.

## Pull requests

1. Branch from an up-to-date `main`.
2. Push and open a PR. Fill in the template — it is short on purpose.
3. Link the issue it closes (`Closes #12`).
4. Mark it draft while it is still moving.
5. Request review. CI must pass and all conversations must be resolved.
6. **Squash merge.** The branch deletes itself afterwards.

Keep pull requests small. A PR that touches forty files is a PR nobody reviews honestly.

## Reviewing

Reviewing is real work and counts as contribution. When you review:

- Say what you actually think. A rubber-stamp approval helps nobody.
- Distinguish blocking problems from suggestions. Prefix optional comments with `nit:`.
- Approve when it is good enough to merge, not when it is perfect.
- If you do not understand the change, that is a finding — ask.

## Definition of done

A change is done when:

- [ ] It does what the issue asked.
- [ ] CI passes.
- [ ] A teammate has reviewed and approved it.
- [ ] Documentation is updated if behaviour or setup changed.
- [ ] A decision worth remembering is recorded as an ADR in `docs/decisions/`.

## Data rules

Non-negotiable, and they come from the course requirements:

- Synthetic, publicly available, or appropriately de-identified data only.
- Never commit real patient data, credentials, API keys, or `.env` files.
- If you think a dataset might be sensitive, ask before committing it.

## Decisions

When the team makes a choice that a future reader would otherwise ask "why?" about —
a framework, a data model, a dropped feature — write it up in `docs/decisions/`. Copy
`0001` as the shape. This costs five minutes now and saves the P1 through P5 write-ups.
