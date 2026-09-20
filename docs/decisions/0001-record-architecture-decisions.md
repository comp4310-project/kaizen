# 1. Record architecture decisions

**Status:** Accepted
**Date:** 2026-09-19

## Context

This project runs one term across four people and produces five graded deliverables, each
of which asks us to justify our technical decisions. Decisions made in September will need
defending in November, by which point the reasoning will have evaporated.

Chat history is not a record. It is unsearchable, it mixes decisions with noise, and it
does not distinguish "we agreed on this" from "someone suggested this."

## Decision

We record significant technical decisions as Architecture Decision Records in
`docs/decisions/`, following the format introduced by Michael Nygard.

Each record captures the context that forced a decision, the decision itself, and the
consequences we accept by making it. Records are numbered sequentially, immutable once
accepted, and superseded rather than edited.

ADRs are submitted as pull requests so that the record of the discussion sits alongside
the record of the decision.

## Consequences

- Deliverable write-ups can quote decisions made months earlier, with reasoning intact.
- New context for any team member returning to an unfamiliar part of the system.
- A small ongoing cost: roughly five minutes per significant decision.
- A risk we accept: ADRs written after the fact tend to rationalize. Write them when the
  decision is made, not when the report is due.
