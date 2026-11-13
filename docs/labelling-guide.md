# Labelling guide

How we label a comment, for the hand-labelled test set (P3 section 3.1) and for the
classifier's prompt (FR3). The labels come from the Healthcare Complaints Analysis Tool
(HCAT, Gillespie and Reader 2016) so our results can be compared with published work.
Urgency is our own, adapted from HCAT's severity levels.

Every comment gets four labels: sentiment, problem categories, stage of care and urgency.
Label what the comment says, not what you think happened. If you have to guess, use the
"unclear" or "low" option and move on.

All examples below are made up. Personal details are already replaced with tags such as
`<PERSON>` by the time anyone labels a comment.

## Sentiment

One per comment.

| Label | Use when |
|---|---|
| `positive` | The comment is mainly praise or thanks. |
| `neutral` | A suggestion, a question or a plain report with no clear feeling either way. |
| `negative` | The comment is mainly a complaint or describes something going wrong. |

When a comment mixes praise and a complaint, pick the part the writer spends more words on.
If they are about even, choose `negative`, since the complaint is what a QI team acts on.

- "The nurses on 4B were lovely and always came when I rang." `positive`
- "Could the ward have a water jug at each bed?" `neutral`
- "The surgeon was great but I waited 9 hours in ED with no update." `negative`

## Problem categories

Zero or more per comment. A comment that only praises gets none. A comment can have
several, for example a long wait that nobody explained is both institutional processes and
communication.

| Label | HCAT domain | Use when the problem is about |
|---|---|---|
| `quality` | Clinical | The standard of clinical or nursing care: rushed or careless care, poor pain control, basic needs not met. |
| `safety` | Clinical | Errors, near misses and risk of harm: wrong or missed medication, falls, misdiagnosis, a staff member not acting when they should have. |
| `environment` | Management | The building and resources: cleanliness, noise, food, beds, equipment, parking, not enough staff on shift. |
| `institutional_processes` | Management | How the hospital runs: waiting times, delays, admission and discharge processes, paperwork, referrals, bed management. |
| `listening` | Relationships | Concerns being ignored or dismissed: patient or family not believed, pain brushed off, staff concern not acted on. |
| `communication` | Relationships | Information: unclear, wrong, missing or inconsistent explanations, discharge instructions, test results not passed on, handover gaps. |
| `respect_and_rights` | Relationships | Rudeness, lack of dignity or privacy, consent, discrimination. |

Rules for the close calls:

- A wait on its own is `institutional_processes`. Add `communication` only if the comment
  says nobody explained the wait.
- Short staffing is `environment`. If it led to harm or a near miss, add `safety`.
- Medication given late is `quality`. The wrong drug or dose, or a missed dose, is `safety`.
- Staff comments about other teams or handovers usually fall under `communication` or
  `institutional_processes`.

Examples:

- "My mother was left in a wet bed for hours." `quality`
- "I was given the 8am dose of metoprolol twice." `safety`
- "The bathroom on 3A had not been cleaned all weekend." `environment`
- "Discharge took all day because pharmacy had not filled the prescription." `institutional_processes`
- "I told them three times her pain was getting worse and nobody came." `listening`
- "Nobody told us what the scan showed before we went home." `communication`
- "A nurse talked about my diagnosis loudly in front of the whole bay." `respect_and_rights`
- Staff: "Night shift handed over two patients without telling us about their falls risk." `communication`, `safety`

## Stage of care

One per comment: where in the hospital stay the problem (or praise) happened. If a comment
covers several stages, pick the one the main problem is in.

| Label | Use when the comment is about |
|---|---|
| `admissions` | Arriving and getting admitted: ED waits, triage, waiting for a bed, being admitted. |
| `examination_and_diagnosis` | Assessment, tests, scans, results and diagnosis. |
| `care_on_the_ward` | Day to day care during the stay: nursing, medication rounds, food, the room, visiting. |
| `operations_and_procedures` | Surgery, procedures, anaesthesia and recovery straight after. |
| `discharge_and_transfers` | Going home or moving between units or hospitals: discharge planning, instructions, prescriptions to take home, transport. |
| `unclear` | The comment does not say, or it is about the hospital in general. |

- "Triage took four hours and nobody checked on us." `admissions`
- "My CT results took three days to come back." `examination_and_diagnosis`
- "Call bells on the ward went unanswered at night." `care_on_the_ward`
- "The anaesthetist explained everything before my knee surgery." `operations_and_procedures`
- "We were sent home with no instructions about the new blood thinner." `discharge_and_transfers`
- "Great hospital, thank you all." `unclear`

## Urgency

One per comment. This is a suggestion only. In the app a person always confirms it (FR6),
because language models judge severity poorly (Koh et al. 2025).

| Label | Use when |
|---|---|
| `low` | An inconvenience or a minor problem. No harm and no follow-up needed beyond the usual trend review. Praise is always `low`. |
| `medium` | The writer was distressed, care was delayed, or a problem is likely to happen again unless someone looks at it. |
| `high` | Harm, or a real risk of harm: a medication error, a fall, abuse, a missed deterioration, an unsafe discharge. Someone should look at it within a day. |

When unsure between two levels, choose the higher one. Missing an urgent comment costs more
than a false alarm, and a person reviews it either way.

- "The food was cold." `low`
- "We waited six hours with no update and my father was in pain." `medium`
- "He was discharged still confused and fell at home the same night." `high`

## Process

Two members label the first 100 comments separately, without looking at each other's
labels or at any labels from the synthetic data templates. We then measure agreement with
Cohen's kappa for each label (target 0.6 or higher). A third member settles disagreements,
and we update this guide with the reason before labelling the remaining 300. Write any rule
you add here, with an example, so later labels follow it.
