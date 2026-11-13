# Decisions

Dated notes on things we picked and why. A couple of lines each is enough. This exists
because the P1 to P5 reports ask us to justify our technical choices.

## 2026-09-19 Public repo under a team org

GitHub only enforces branch protection for free on public repos, so a private one would
have meant the review rules were suggestions. Org rather than a personal account so the
repo belongs to the team. The org name is deliberately generic because renaming an org
breaks everyone's git remotes, while renaming a repo doesn't.

## 2026-11-06 De-identification uses our own date and ID patterns

Presidio's spaCy-based date recognizer also removed lengths of time ("waited 3 days"),
and its location recognizer removed unit names. Both are things the classifier and the
unit filters need, so we only use spaCy for names and match calendar dates, Ontario health
card numbers, record numbers and phones with our own patterns. Names written in lower case
are still missed.

## 2026-11-13 Labelling uses Claude Haiku 5.5 through LiteLLM

As P3 planned, every LLM call goes through LiteLLM, so changing provider or moving to a
local model is a change of model name. Bulk labelling uses Claude Haiku 5.5 at low effort,
the low-cost model P3 asked for. The reply must match our label schema; LiteLLM passes the
schema on to Claude, and we check every reply again with pydantic before saving it.
`KAIZEN_LABEL_MODEL` and `KAIZEN_LABEL_EFFORT` change the model and effort, and both are
stored with every label.
