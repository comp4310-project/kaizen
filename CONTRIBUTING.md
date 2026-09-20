# Contributing

`main` is protected. Everything goes through a pull request with one review.

## Branches

`feat/` `fix/` `docs/` `chore/` plus a short description.

```
feat/feedback-clustering
docs/p1-proposal
```

## Commits

Start the subject with the area you touched, then what you did:

```
ingest: handle feedback rows with no ward
docs: draft P1 problem statement
```

Keep the subject short. Add a body when the reason isn't obvious from the diff. The diff
already shows what changed, so the message is for explaining why.

Commit often. The markers look at the commit history to work out who did what, so a term's
work landing in five big commits at the end looks bad and is hard to defend.

## Pull requests

- Branch off an up-to-date `main`
- Link the issue it closes (`Closes #12`)
- Draft it while you're still working
- Needs one approval and green CI
- Squash merge, the branch deletes itself
- Keep them small, big PRs don't get read properly

Leave actual comments when you review. A PR approved in thirty seconds with no comments
looks the same as pushing straight to main.

## Don't commit

Real patient data, `.env` files, API keys, or anything over 5MB. CI checks for most of it.

## Decisions

If we pick a framework or drop a feature, add a dated line to `docs/decisions.md`. We have
to justify our technical choices in the reports and nobody will remember why in November.
