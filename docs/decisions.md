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

## 2026-11-13 Labels follow HCAT, urgency leans high

Categories and stages of care come from the Healthcare Complaints Analysis Tool instead of
our own lists, because it has been tested for reliability and lets us compare our stage
results with Koh et al. We added an "unclear" stage so neither labellers nor the model
are forced to guess. Urgency is our own three levels; when unsure, labellers pick the
higher one, since a missed urgent comment is the costly mistake and a person confirms it
anyway. Details in `docs/labelling-guide.md`.

## 2026-11-13 Issue finding without BERTopic's PyTorch

P3 named BERTopic. Its sentence-transformers dependency installs PyTorch, which on CI is a
download of over a gigabyte for every run. We use the same steps BERTopic does (sentence
embeddings, UMAP, HDBSCAN, class-based TF-IDF keywords) with fastembed, which runs the
same all-MiniLM-L6-v2 model through ONNX, and scikit-learn's HDBSCAN. On a hand-written
test of 62 comments with 4 planted problems it found all 4, though one was split in two.

## 2026-11-13 Passage search without Chroma

P3 named Chroma for searching the documents behind suggestions. Installing it next to our
pinned packages adds 50 more, including a Kubernetes client, gRPC and OpenTelemetry
exporters, to search a corpus P3 sizes at 30 to 50 documents. We embed each passage once and
compare a query with every passage in numpy instead. At a few thousand passages that is
exact and takes milliseconds. The vectors are saved with a fingerprint of the passage texts
and model name, so they are rebuilt only when a document or the model changes. If the
corpus ever grows past what fits in memory, Chroma is still the next step.

## 2026-11-13 The citation check compares words, not characters

NFR2 drops any suggestion whose quote is not in its source. A character-for-character match
would drop good quotes over a curly apostrophe or a line break from PDF extraction, so the
check compares the sequence of words and ignores case and punctuation. It still rejects a
quote with any word changed, added or removed, a quote joined with "...", and quotes under
six words, since a phrase that short is found in almost any passage.

## 2026-11-14 How suggestion ratings are scored

P3 Table 9 asks for 70% of suggestions to "score 5 or 6" from two raters without saying how
two raters combine. We average the two totals, so a 6 and a 4 counts and a 5 and a 4 does
not, and a suggestion is unsafe if either rater says so, since one missed unsafe suggestion
is the costly mistake. The comparison model gets the same issues and prompt with no
documents, so it has nothing to cite; its citation support is "n/a" and it is compared on
relevance and actionability only. Both sets go into one shuffled sheet with the answers in a
separate key. Raters can still spot most comparison items by their empty citations, so this
reduces bias from rating one set in a block rather than removing it.
