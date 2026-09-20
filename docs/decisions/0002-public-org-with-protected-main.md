# 2. Public organization repository with protected `main`

**Status:** Accepted
**Date:** 2026-09-19

## Context

P0 requires a shared repository accessible to all team members. Beyond satisfying that
requirement, we wanted a setup that enforces code review rather than relying on everyone
remembering to ask for one.

Three constraints shaped the choice:

1. GitHub enforces branch protection and rulesets **free only on public repositories**.
   On private repositories it requires a paid plan (Pro for personal accounts, Team for
   organizations). An unenforced rule is a suggestion.
2. Renaming a GitHub **organization** breaks team mentions, API references, and every
   member's git remote. Renaming a **repository** is nearly free — GitHub redirects both
   web and git traffic.
3. The team name and project topic were not settled when the repository was needed.

## Decision

- Host under a GitHub organization, `comp4310-project`, rather than a personal account, so
  the repository is team-owned and outlives any individual account.
- Name the organization generically. The identity-bearing, changeable name lives on the
  repository, which can be renamed once the team agrees without disrupting anyone.
- Make the repository **public**, accepting visibility in exchange for enforced review.
- Protect `main` with a ruleset: no direct pushes, one approving review required, stale
  approvals dismissed on new commits, conversations resolved before merge, linear history,
  squash merges only.

## Consequences

- Every change to `main` has been read by a second person. This is the main thing we
  wanted and it is now structural rather than cultural.
- Repository owners are bound by the same rules, which is the point.
- Other teams can read our work. We judged copying risk to be low relative to the benefit,
  and the repository doubles as a portfolio artifact afterwards.
- If the team later objects to public visibility, switching to private silently disables
  enforcement of every rule above. That trade must be made explicitly, not by flipping a
  toggle.
