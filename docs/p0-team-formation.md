# P0 — Team Formation and Topic Selection

COMP 4310 — Web Health Informatics, Lakehead University
Due: Sunday, September 20, 2026, 11:59 PM — one PDF per team on D2L

> Draft. Anything marked TBD needs confirming with the team before this gets submitted.

## 1. Team Name

**Kaizen**

*Kaizen* (改善) means continuous improvement through lots of small changes, usually
suggested by the people doing the work. It's a term used in hospital operations, and it
describes what we're trying to build.

## 2. Team Members

| Full name | Lakehead email | GitHub |
|-----------|----------------|--------|
| Mohammed Asrar Ali | TBD | @Asrar-ali |
| TBD | TBD | @Muazhuja01 |
| TBD | TBD | TBD |
| TBD | TBD | TBD |

## 3. Preliminary Project Title

Kaizen: Turning Hospital Feedback into Actionable Quality Improvements

## 4. Project Theme / Area

Student-proposed project.

It overlaps with several of the suggested themes — P11 (health report generation), P6
(analytics dashboard), P5 (summarization) and P12 (search and recommendation) — but
doesn't fit neatly into one, so we're proposing it as our own topic and would like
approval for the scope below.

## 5. Brief Project Idea

We want to build a web system that helps hospitals turn feedback from patients, doctors,
nurses and visitors into improvements they can actually act on. Hospitals collect a lot of
this feedback but rarely analyse it properly, so problems that keep recurring go unnoticed.
The system would use NLP and large language models to group comments into recurring
themes, work out where in the hospital's workflow each problem is happening, and suggest
possible fixes based on hospital policies and published research on quality improvement.
The users would be quality-improvement teams and hospital managers. Everything the system
produces is a suggestion for a person to review, not a decision.

## 6. Preliminary Technology Stack

Nothing here is decided yet.

| Layer | What we're considering |
|-------|------------------------|
| Frontend | React, TypeScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Search | Sentence embeddings, vector store |
| NLP / AI | LLM API or a local model, with retrieval over a policy and research corpus |
| Clustering | scikit-learn, topic modelling |
| Other | GitHub Actions for CI |

## 7. Shared Repository

https://github.com/comp4310-project/kaizen

Public repo under our team organisation. All members have access. `main` is protected, so
changes go through pull requests with a review.

## Data and limitations

We'll only use synthetic, public, or properly de-identified data — no real patient
information at any point. This is a course prototype, not a clinically validated system,
and anything the AI generates is decision support for a human to check rather than an
authoritative answer. Part of the work is testing whether the generated suggestions
actually match the data they came from.

## Questions for the instructor/TA

1. Is this scope alright as a student-proposed project, or would you rather we ran it
   under P11?
2. Is synthetic feedback data acceptable? Real hospital feedback doesn't seem to be
   publicly available at any useful scale.
3. How far should we take the impact-estimation part in one term?
