# P1: Project Proposal

COMP 4310 Web Health Informatics, Lakehead University
Submitted to D2L. Grade: 94/100 (feedback in [feedback.md](feedback.md#p1-project-proposal)).

This mirrors what went in the PDF. Student IDs are in the submitted version only, since
this repo is public.

## 1. Project Overview

| | |
|---|---|
| Team name | Kaizen |
| Project title | Kaizen: Turning Hospital Feedback into Actionable Quality Improvements |
| Team members | Hemanth Reddy Basireddy, Hujaifa Muaz, Mohammed Asrar Ali, Aansh Amitabh Arora, Bhavya Bhatt |
| Repository | https://github.com/comp4310-project/kaizen |

Hospitals collect a lot of written feedback from patients, families and staff, but most of it is never read closely. Kaizen is a web app that removes personal details from that feedback, sorts it by topic and sentiment, groups similar comments into recurring issues, and links each issue to a stage of the care pathway, like triage or discharge. For a chosen issue it drafts improvement ideas based on policy documents and quality-improvement (QI) literature, and a staff member accepts, edits or rejects each one. It is meant for QI teams, patient-relations staff and unit managers. We only use synthetic and public data.

## 2. Problem Description

Hospitals collect feedback through surveys, complaints, staff comments and public reviews. The most useful part is usually the written comment, but reading thousands of them by hand takes time most hospitals do not have [1], so reports end up focusing on the scores. Studies of how patient-experience data is used find that it often leads to only small changes, and hospitals struggle to show what actually improved [2]. In practice this means:

- Comments pile up faster than a small QI team can read them, so problems are found late.
- Patient, nurse and physician comments sit in separate places even when they describe the same problem. For example, patients find discharge instructions confusing while nurses report missing paperwork.
- "Waiting" is not actionable until you know where it happens (triage, imaging, discharge) and on which unit.

This affects patients and families, whose reports lead nowhere; nurses and physicians, who keep working around the same process problems; QI staff, who are accountable for improvement without a practical way to read their own data; and administrators, who have to report on quality to boards and accreditors.

It is a health informatics problem rather than just a software one. The feedback often contains personal health information, so privacy law such as Ontario's PHIPA applies [3]. It also uses clinical language (abbreviations, ward names, medications) that generic sentiment tools can miss, and the results have to fit structures hospitals already use, such as patient-experience domains, care-pathway stages and Plan-Do-Study-Act (PDSA) improvement cycles.

## 3. Motivation and Significance

Patient experience is linked to clinical safety and effectiveness [4], so a comment about unclear medication instructions may point to a real safety risk and not just a comfort issue. The gap is in using feedback, not collecting it [2]. At the same time, NLP methods for free-text feedback have matured enough to be a practical way to get insight from large volumes of comments [1], and retrieval-augmented generation [5] makes it possible to draft suggestions from real documents instead of the model's memory.

If it works, a QI team could read all of its feedback instead of a sample, spot growing issues sooner, and start each improvement cycle from a sourced draft. It fits health informatics because it is about handling, structuring and analysing health-related text and getting it to the people who make decisions.

## 4. Project Objectives

By the end of the term, Kaizen should let a QI team do the following, which addresses the gaps in Section 2:

1. Bring feedback from patients and staff into one secure web app, with personal details removed before anything is stored.
2. Turn thousands of free-text comments into a short, ranked list of recurring issues by labelling sentiment and topic and clustering similar comments.
3. See where each issue happens, by mapping it to a care-pathway stage and unit and showing whether patients, staff or both report it.
4. Get improvement ideas backed by cited policy and literature, where a person always accepts, edits or rejects each one.
5. Trust the results, by testing against a hand-labelled sample (aiming for an F1 of about 0.7 or higher on classification) and rating the quality of the suggestions.

## 5. Intended Users and Stakeholders

- QI and patient-relations staff are the main users. They review ranked issues, read the supporting comments, request suggestions and record what was done.
- Unit managers look at issues and trends for their own ward.
- Administrators need an organisation-wide summary and exports for board and accreditation reports.

Patients and families submit feedback through a simple form and want to know it is read and kept private. Nurses and physicians both give feedback and can check whether a suggestion makes clinical sense. Since we have no hospital partner, we will test the system against role-based scenarios based on published QI practice [2].

## 6. Preliminary Proposed Solution / Methodology

Kaizen is a web app built as a pipeline. The details may change after the literature review in P2.

| Step | Approach and tools we are considering |
|---|---|
| Ingest and de-identify | Web form and CSV import. Rule-based patterns and spaCy NER remove names, dates and record numbers. React, FastAPI, MySQL. |
| Classify | Sentiment, urgency and topic labels using Hugging Face transformers, plus a sentence embedding for each comment. |
| Find issues | Cluster the embeddings (UMAP + HDBSCAN or BERTopic), have an LLM write a short label, and map each issue to a care-pathway stage. |
| Suggest | Retrieve passages from policy documents and QI papers, then have an LLM draft two or three actions with citations [5]. |
| Dashboard | React dashboard with ranked issues, trends, drill-down to comments, accept/edit/reject and an improvement tracker. |

**Role of AI.** AI does three jobs: grouping thousands of comments into a few issues (embeddings and clustering), labelling them with topics and pathway stages (classification), and drafting suggestions from retrieved documents (RAG). Because LLMs can make things up, suggestions are limited to retrieved text, must cite their sources, and are never applied without a person's decision.

**Data and evaluation.** No real patient data will be used. We will combine public feedback or review data, synthetic comments generated from scenario templates and checked by the team, and a hand-labelled set of about 300-500 comments. We will report precision, recall and F1 for classification, check cluster quality against our labels, and have two team members rate a sample of suggestions for relevance, actionability and whether they match the cited source.

## 7. Project Scope and Feasibility

| In scope | Out of scope |
|---|---|
| Web app with feedback submission, import and dashboard | Integration with real hospital systems (EHR, portals) |
| De-identification, classification and clustering of English comments | Other languages, audio, real-time alerts |
| Pathway mapping and RAG suggestions with human review | Real hospital deployment or user study; decisions about individual patients |
| Offline evaluation on a labelled sample | Privacy certification or compliance sign-off |

**Minimum outcome.** At the least, we will deliver a working app that de-identifies, classifies and clusters a synthetic and public feedback set into ranked issues mapped to pathway stages, with a dashboard and an evaluation. The suggestion engine would then run on a smaller document set.

**Constraints.**

- Public hospital feedback data may be limited, so we will add documented synthetic data and say so in the report.
- Labelling takes time, so we will cap the labelled set and double-label part of it to check agreement.
- LLM suggestions can be wrong, so we will rely on retrieval, citations and human review.
- With no clinical partner, this is a prototype and we cannot measure real-world impact.
- Five people and one term, so work is split into workstreams: ingestion and privacy, NLP, RAG, front end, and evaluation.

## References

1. M. Khanbhai, P. Anyadi, J. Symons, K. Flott, A. Darzi, and E. Mayer, "Applying natural language processing and machine learning techniques to patient experience feedback: a systematic review," BMJ Health & Care Informatics, vol. 28, no. 1, e100262, 2021.
2. H. Gleeson, A. Calderon, V. Swami, J. Deighton, M. Wolpert, and J. Edbrooke-Childs, "Systematic review of approaches to using patient experience data for quality improvement in healthcare settings," BMJ Open, vol. 6, no. 8, e011907, 2016.
3. Government of Ontario, Personal Health Information Protection Act, 2004, S.O. 2004, c. 3, Sched. A. https://www.ontario.ca/laws/statute/04p03
4. C. Doyle, L. Lennox, and D. Bell, "A systematic review of evidence on the links between patient experience and clinical safety and effectiveness," BMJ Open, vol. 3, no. 1, e001570, 2013.
5. P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive NLP tasks," in Advances in Neural Information Processing Systems, vol. 33, 2020, pp. 9459-9474.
