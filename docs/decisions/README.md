# Architecture Decision Records

Short documents recording decisions that a future reader would otherwise have to
reverse-engineer. One decision per file.

## Why we keep these

The P1–P5 deliverables ask us to justify our technical choices. Writing the reason down
when we make the decision takes five minutes. Reconstructing it in November, from memory,
takes an afternoon and produces a worse answer.

## When to write one

Write an ADR when the team chooses between real alternatives and the choice constrains
later work: a framework, a data model, a deployment target, a feature deliberately cut.

Do not write one for a choice nobody would question.

## How

Copy the structure of `0001-record-architecture-decisions.md`. Number sequentially.
Name files `NNNN-short-title-in-kebab-case.md`. Open it as a pull request so the team
actually discusses it.

Statuses: `Proposed` · `Accepted` · `Superseded by ADR-NNNN` · `Rejected`

Do not edit an accepted ADR to change the decision. Write a new one that supersedes it —
the trail of what we thought at the time is the point.

## Index

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-public-org-with-protected-main.md) | Public organization repository with protected `main` | Accepted |
