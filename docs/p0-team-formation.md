# P0 — Team Formation and Topic Selection

**COMP 4310 — Web Health Informatics**
Department of Computer Science, Lakehead University
Due: Sunday, September 20, 2026, 11:59 PM · Submission: one PDF per team via MyCourseLink (D2L)

> **Draft.** Fields marked _TBD_ need confirmation from the team before this is exported to
> PDF and submitted.

---

## 1. Team Name

**Kaizen**

*Kaizen* (改善) is the practice of continuous improvement driven by many small changes
surfaced by the people closest to the work. It entered healthcare through Lean hospital
operations, and it names exactly the loop this project tries to close.

## 2. Team Members

| Full name | Lakehead email | GitHub |
|-----------|----------------|--------|
| Mohammed Asrar Ali | _TBD_ | @Asrar-ali |
| _TBD_ | _TBD_ | @Muazhuja01 |
| _TBD_ | _TBD_ | _TBD_ |
| _TBD_ | _TBD_ | _TBD_ |

## 3. Preliminary Project Title

**Kaizen: Turning Multi-Stakeholder Hospital Feedback into Actionable Quality Improvements**

## 4. Project Theme / Area

**Student-proposed project.**

The work draws on several suggested themes without matching any single one: P11
(AI-Assisted Health Report Generator), P6 (Health Data Analytics Dashboard), P5
(Clinical Note Summarization), and P12 (Health Information Search and Recommendation).
We are seeking instructor/TA approval for the student-proposed scope described below.

## 5. Brief Project Idea

We plan to develop a web-based system that helps hospitals convert unstructured feedback
from patients, doctors, nurses, and visitors into prioritized, actionable quality
improvements. Feedback of this kind is collected in volume but rarely analyzed
systematically, so recurring problems remain invisible. The system will use NLP and large
language models to cluster comments into recurring themes, identify where each theme
originates in hospital workflows, and propose candidate interventions grounded in hospital
policies and published quality-improvement research. It will also estimate the expected
impact of proposed changes. Intended users are quality-improvement teams, unit managers,
and administrators. All outputs are decision support, evaluated for faithfulness rather
than treated as authoritative.

## 6. Preliminary Technology Stack

Preliminary and subject to change as the design develops.

| Layer | Candidate technologies |
|-------|------------------------|
| Frontend | React, TypeScript |
| Backend | Python, FastAPI, REST API |
| Database | PostgreSQL |
| Semantic search | Sentence embeddings, vector store |
| NLP / Generative AI | LLM API or locally hosted model; retrieval-augmented generation over a policy and literature corpus |
| Clustering / topic modelling | scikit-learn, topic modelling over embeddings |
| Visualization | Interactive dashboard |
| Collaboration and CI | GitHub, GitHub Actions |

## 7. Shared Repository

https://github.com/comp4310-project/kaizen

Public repository under the team organization `comp4310-project`. All team members have
access. `main` is protected: changes land through reviewed pull requests.

---

## Data and Ethics

Consistent with the course requirements, the project will use synthetic, publicly
available, or appropriately de-identified feedback data only. It will not require access
to confidential patient information, will not be represented as a clinically validated
system, and will present AI-generated output as decision support for human review rather
than as authoritative decisions. Evaluating output faithfulness, and documenting the
system's limitations, are explicit parts of the project.

## Open questions for instructor/TA

1. Is the student-proposed scope appropriate, or should it be framed under P11?
2. Is a synthetic feedback corpus acceptable, given that real hospital feedback data is
   not publicly available at useful scale?
3. How rigorous should the impact-estimation component be for a one-term project?
