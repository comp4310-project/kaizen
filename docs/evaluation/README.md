# Evaluation results

Results against P3 Table 9, from runs in November 2026. Two things about how they were
produced matter for reading every number below.

**No human raters were used.** P3 planned two team members to label comments and rate
issues and suggestions, and five classmates for the usability test. We changed that plan:
every judgement that needed a person was made by a separate LLM agent given a persona and
the same instructions a person would get (the labelling guide, the rating rubric, the four
usability tasks). They are reported as simulated annotators, raters and participants. Two
personas built on the same underlying model agree with each other more than two people
would, so agreement figures here are likely too high.

**No hosted model was used.** We had no Anthropic API key, so every LLM step ran on
qwen2.5:7b through Ollama on a laptop GPU (RTX 4060, 8GB), switched in through LiteLLM as
P3 section 5.2 allows. P3 planned Claude Haiku for labelling and Claude Opus for
suggestions, which are far larger models. The LLM numbers are what a small local model does,
not what the design can do.

## Summary

| Check (P3 Table 9) | Data | Result | Target | Met |
|---|---|---|---|---|
| De-identification recall | synthetic test set, 300 details | 98.3% | 95% | yes |
| De-identification: tags removing non-personal text | synthetic test set | 0% | under 5% | yes |
| De-identification: tags removing non-personal text | 1,625 real comments | 0 of 7 (was 32 of 39) | under 5% | yes, after #28 |
| Sentiment macro F1, local LLM | 150 hand-labelled real comments | 0.67 | 0.75 | no |
| Category micro F1, local LLM | same | 0.37 | 0.70 | no |
| Stage accuracy, local LLM | same | 0.01 | 65% | no |
| Urgency: high comments flagged, local LLM | same, 10 high | 4 of 10 | 80% | no |
| Baseline, trained on synthetic, all four labels | same | 0.27 / 0.24 / 0.09 / 0.10 | as above | no |
| Baseline, all four labels | 300 held-out synthetic | 0.996 / 0.955 / 97% / 95% | as above | yes, but see below |
| Issues: good issues | real comments, 8 issues | 1 of 8 | 70% | no |
| Issues: built-in problems found | synthetic | 5 of 8 | 6 of 8 | no |
| Rising problem flagged | synthetic | yes, no false flags | flagged | yes |
| Suggestions scoring 5 or 6 | 13 with documents | 15% | 70% | no |
| Unsafe suggestions | 26 | 0 | 0 | yes |
| SUS, round 1 | 5 simulated participants | 64.0 | 68 | no |
| SUS, round 2 after #30 | 5 new simulated participants, same profiles | 69.5 | 68 | yes |
| Processing time, no LLM | 1,000 synthetic comments | 9 s | 15 min | yes |
| Processing time, local LLM labelling | 1,625 real comments | 28.5 min (17.5 per 1,000) | 15 min | no |

`python -m kaizen.evaluate OUT_DIR` reruns the synthetic rows (#29). The real-comment rows
need the FFT file from `backend/scripts/fetch_fft_comments.py` and the local model run.

## Data

Real: 1,625 NHS Friends and Family Test comments from North East Ambulance Service ("See and
Convey"), from NHS England's pxtextmining repository (MIT licence), fetched by script and
never committed. They are ambulance comments from patients and families only, so they
cannot test the staff side of FR5, and most fall outside the hospital stages of care.

Synthetic: 1,200 comments from `backend/scripts/make_synthetic.py` (#29), 30% staff, with 8
built-in problems, split 900 for training and 300 held out.

## Labelling (FR3)

Two simulated annotators (an ED charge nurse and a non-clinical patient experience officer)
labelled 150 randomly chosen real comments from the guide, without seeing each other's
work. A third persona, acting as the QI lead who wrote the guide, settled the 47 comments
where they differed. The labels, keyed by FFT comment id and without text, are in
[fft-labels.csv](fft-labels.csv).

| Label | Exact agreement | Cohen's kappa |
|---|---|---|
| Sentiment | 98% | 0.97 |
| Urgency | 93% | 0.79 |
| Categories (whole set) | 94% | n/a |
| Stage of care | 71% | 0.07 |

Stage is the problem. The guide defines stage as where in the hospital stay something
happened, and a wait for an ambulance or care at the scene is not in the hospital stay. The
adjudicator followed the guide and marked 148 of the 150 `unclear`. Annotator 1 had put many
of them under `admissions`, and so did the model. The guide needs a rule for pre-hospital
comments before stage means anything on this data.

Against the adjudicated labels, qwen2.5:7b scored sentiment macro F1 0.67, category micro
F1 0.37, stage accuracy 0.01 (it chose `admissions` for nearly everything and never
`unclear`) and found 4 of the 10 high-urgency comments. On all 1,625 comments its sentiment
macro F1 against the FFT project's own 1 to 5 scores (1-2 positive, 3 neutral, 4-5
negative) was 0.58. The TF-IDF baseline, cross-validated on those same FFT scores, reached
0.65.

The baseline's 0.996 on synthetic data and 0.27 on the real comments come from the same
model. Trained on synthetic templates, it learns the templates. This is the risk P3 section
5.1 raised about reporting synthetic and public results separately, and the synthetic
numbers should not be quoted on their own.

## Issues (FR4)

On the real comments, the first run produced 7 issues, and 6 were clusters of non-answers
such as "Nothing" and "Did not answer", named after problems none of their comments
mentioned ("Discharge Summary Omissions" for ten comments saying "Nothing"). Issue building
now skips comments with no problem category and the usual survey non-answers (#27). The
next run grouped 345 comments into 8 issues.

Two simulated raters (a QI analyst and an ED nurse educator) read 10 comments from each.

| Rank | Name | Same problem (A / B) | Name specific (A / B) |
|---|---|---|---|
| 1 | Ambulance Arrival Delays | 9 / 9 | yes / yes |
| 2 | Ambulance dispatch process inefficient | 7 / 7 | no / no |
| 3 | Ambulance Arrival Delays | 4 / 5 | no / yes |
| 4 | 999 Response Delay | 3 / 6 | no / no |
| 5 | Long Wait Times in Emergency | 9 / 9 | no / no |
| 6 | Ambulance Dispatch and Availability | 4 of 8 / 4 of 8 | no / no |
| 7 | Long Wait Times on Floor | 9 / 9 | no / no |
| 8 | Long Waiting Times at Admissions | 8 of 9 / 8 of 9 | no / no |

Both raters found 1 of 8 good by P3's rule (8 of 10 about one problem and a specific name).
Four groups are coherent; the names fail. The 7B model adds places the comments never
mention ("on Floor", "at Admissions"), and ambulance waits are split across issues 1, 5 and
7. On synthetic data, 5 of the 8 built-in problems were found; discharge medication delay,
the main test case, split into two clusters of 19 and 17.

## Suggestions (FR7, NFR2)

26 suggestions drafted for the first real-data issues, half with the documents and half by
the same model with none, shuffled and rated blind by two simulated raters on P3's 0 to 2
scales.

| | Relevance | Actionability | Citation support | Unsafe |
|---|---|---|---|---|
| With documents (13) | 1.31 | 0.92 | 0.61 | 0 |
| Without documents (13) | 1.19 | 0.77 | n/a | 0 |

15% of the suggestions with documents scored 5 or 6. Every quote passed the citation check,
but support averaged 0.61 of 2: the quotes exist in the cited passage and often do not back
the change. The check proves a quote is real, not that it is relevant. These suggestions
were drafted for the issues before #27, most of which were non-answer clusters, which pulls
relevance down. Rater agreement (weighted kappa): relevance 0.76, actionability 0.37,
citation support 0.58.

## De-identification (FR2)

On the synthetic test set recall was already above target. On the real comments 32 of the
33 name tags removed something that was not a name: Mum, Dad, Gran, a hospital (RVI), the
ambulance service (NEAS), misspelt drug names, "However". After #28, 1 name tag remains and
it is a real first name. The test set now includes 64 such hard cases, so the under-5% target
is measured on every pull request. Recall of names on the real comments is not measured,
because nobody has marked the names in them.

## Usability (NFR4)

Five simulated participants did the four tasks in [frontend-usability.md](../frontend-usability.md)
in the browser on a seeded study database: a QI analyst, a surgical nurse manager using
only the mouse, a data analyst using only the keyboard, a 58-year-old non-clinical patient
experience officer, and a junior QI coordinator on a tablet-sized screen.

| Participant | Task 1 | Task 2 | Task 3 | Task 4 | SUS |
|---|---|---|---|---|---|
| P1 QI analyst | yes | yes | yes | probably | 70.0 |
| P2 nurse manager | yes | yes | yes | partly | 57.5 |
| P3 keyboard only | yes | yes | yes | probably | 75.0 |
| P4 non-clinical | yes | yes | yes | unsure | 42.5 |
| P5 tablet | yes | yes | yes | probably | 75.0 |

Mean SUS 64.0 against 68. The top issue's comments were one click from the issues page for
everyone. All five were unsure whether task 4 worked, because the CSV download showed
nothing on screen. The other repeated findings: "Edit labels" left focus on the button and
put Save below seven checkboxes; "Only patients" and "Patient or family" named the same
group differently; the comparison rows led nowhere; jargon such as "CSV", "outliers" and
"suggested by the model" stopped the non-clinical participant. The automated axe scan
found no WCAG 2.1 A or AA violations.

#30 fixed those: a message next to the download button naming the file and row count, focus
moved into the label form with Save right after the selects, one name for the patient
group, plain wording for automatic labels, typical comments and outliers, a table that fits
a tablet, and keyboard-friendly filters. Round 2 used five new participant instances with
the same five profiles, each on a fresh database.

| Participant | Task 1 | Task 2 | Task 3 | Task 4 | SUS (round 1) |
|---|---|---|---|---|---|
| R2-P1 QI analyst | yes | yes | yes | yes | 72.5 (70.0) |
| R2-P2 nurse manager | yes | yes | yes | yes | 67.5 (57.5) |
| R2-P3 keyboard only | yes | yes | yes | yes | 75.0 (75.0) |
| R2-P4 non-clinical | yes | yes | yes | yes | 47.5 (42.5) |
| R2-P5 tablet | yes | yes | yes | yes | 85.0 (75.0) |

Mean SUS 69.5, above the target of 68. Every participant finished task 4, and the keyboard
participant needed 21 key presses for task 3 against 42 before. R2-P1 reported no download
message; we checked the page afterwards and the message was there, so that participant
missed it. Two participants added up their own SUS wrongly; the scores above are recomputed
from their item answers.

What round 2 still found: the label form shows Save and Cancel twice, the comparison counts
labels nobody has checked yet without saying so, the comparison rows still lead nowhere,
and the non-clinical participant still found "outliers", "Rising" and "Main stage" unclear
and scored 47.5. A sample of five personas from one model family is small and probably
generous, so 69.5 is a sign the fixes helped, not proof the target is met with real users.

## What these results say

Grouping and the dashboard work: the top real issue, ambulance arrival delays, is coherent
and correctly named, and participants reached its comments in one click. The weak parts are
everything the 7B model writes: labels, issue names and suggestions. Rerunning with the
models P3 planned is the obvious next test, and `kaizen.evaluate --llm` is wired for it.
The stage-of-care label does not fit pre-hospital comments and needs a rule in the guide.
And synthetic data flatters a model trained on it so much that only the real-comment
numbers should be used to judge FR3.
