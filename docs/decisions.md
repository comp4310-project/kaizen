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

## 2026-11-14 The first documents are sample policies only

P3 planned 30 to 50 documents: Ontario quality standards, QIP guidance and sample policies
we write ourselves. There was no time before the deadline to collect the Ontario documents
and check whether their licences let us copy them into a public repo, so `documents/` holds
16 sample policies we wrote for a fictional hospital, each marked as such in its header. They
cover the problems built into the synthetic data and the HCAT categories. Suggestions cited
from them show the method works, but they are not evidence of what Ontario guidance says,
and the report has to say so. Adding a real document is one Markdown file with a header.

## 2026-11-14 Real comments from the NHS FFT, real text from Ontario law

P3 planned public comments from pxtextmining "if the licence allows". The repository is
MIT licensed and its README says the two trusts in `v6framework_230831.csv` agreed to publish
their comments. We use only North East Ambulance Service's "See and Convey" comments (1,625
with text), filed under `ED`, because the rest are mental health, forensic, children's,
NHS 111 and patient transport services, outside P3's scope and in places more sensitive. The
Care Opinion file in the same repository is CC BY-NC-SA and covers the same community and
mental health services, so it is not used. The comments are fetched by script from a pinned
commit with a SHA-256 check and are not committed. Their dates mix day-first and month-first
formats; 691 could be read either way and are read day first, which only affects the
rising-issue flag.

Ontario Health's terms require written permission to reproduce its quality standards and QIP
guidance outside personal use, so none are in `documents/`. Ontario statutes may be
reproduced without permission if the text is accurate, credited to the King's Printer and
marked as not official, so sections 2 to 8 of the Excellent Care for All Act (quality
committees, surveys, patient relations, the patient declaration of values and annual quality
improvement plans) are included, checked line by line against the official Word file.

Running the real comments through de-identification showed a problem the synthetic test set
did not: of 33 PERSON tags, one was a name. The rest removed words such as Mum, Dad, Gran,
the hospital (RVI), the ambulance service (NEAS), a town, drug names (Entonox, midazolam,
dexamethasone, some misspelt), covid, typos ("Fromm", "fone"), kisses ("Xx") and
sentence-initial words ("However", "Timescale"). Counting every tag, 32 of 39 (82%) removed
text that is not personal, against the P3 target of under 5%. It goes in the evaluation as
found.

The fix, in `kaizen/deid/person_rules.py`, drops a PERSON tag when the word cannot be a name
(kinship and role words, acronyms of 2 to 5 capitals, drug and condition names with close
misspellings, lower case words, words with no vowel or with digits or dots) and, for a single
word no cue found, when spaCy reads it as an ordinary word once it is lower-cased. A new cue
catches "Bill the paramedic". After the fix the same 1,625 comments get 7 tags: 1 PERSON (the
one name), 5 dates and 1 incident number, all personal, so 0 of 7 remove text that is not
personal. We only know about names spaCy tagged; names it never tagged are not counted.

The test set now has hard negatives of the same kinds (kinship words, acronyms, drugs and
conditions, typos and kisses, 64 spans written for the set). On it the old code removed text
that was not personal in 29 of 322 tags (9.0%) with 97.7% recall; the new code has 0 of 295
(0.0%) and 98.3% recall. The trade-offs: a name typed in capitals ("JILL") is missed, and so
is a surname written alone that ends like a town ("Hamilton was kind"), but not "Dr Hamilton".

- 2026-11-15: Evaluation uses the existing TF-IDF baseline and keyword issue names when no provider key is available. Synthetic intent scores, public FFT sentiment scores and future human-label scores stay separate. NFR3 timings use real processing and SQLite through FastAPI TestClient, so they do not establish browser or hosted-model performance.
