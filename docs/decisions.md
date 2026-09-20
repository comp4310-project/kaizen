# Decisions

Dated notes on things we picked and why. A couple of lines each is enough. This exists
because the P1 to P5 reports ask us to justify our technical choices.

## 2026-09-19 Public repo under a team org

GitHub only enforces branch protection for free on public repos, so a private one would
have meant the review rules were suggestions. Org rather than a personal account so the
repo belongs to the team. The org name is deliberately generic because renaming an org
breaks everyone's git remotes, while renaming a repo doesn't.
