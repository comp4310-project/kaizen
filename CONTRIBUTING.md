# Contributing

`main` is protected. Everything goes through a pull request with one review.

## Branches

`feat/` `fix/` `docs/` `research/` `chore/` plus a short description.

```
feat/feedback-clustering
docs/p1-proposal
```

## Commits

Start with `feat:` `fix:` `docs:` `research:` or `chore:`. Keep the summary short. Add a
body if the reason isn't obvious from the diff.

```
feat: add clustering endpoint
docs: draft P1 problem statement
```

## Pull requests

- Branch off an up-to-date `main`
- Link the issue it closes (`Closes #12`)
- Draft it while you're still working
- Needs one approval and green CI
- Squash merge — the branch deletes itself
- Keep them small, big PRs don't get reviewed properly

## Don't commit

Real patient data, `.env` files, API keys, or anything over 5MB. CI will catch most of it.

## Decisions

If we pick a framework or drop a feature, write a few lines in `docs/decisions/`. We have
to justify our technical choices in the P1–P5 reports and nobody will remember why in
November.
