# Instructor feedback

Feedback we got on each deliverable, copied from D2L, plus what we changed because of it.
Newest first.

## P2: Literature and Existing-System Analysis

**96/100**

| Criterion | Mark |
|---|---|
| Project Context | 10/10 |
| Research and Existing Solutions | 28/30 |
| Comparative Analysis | 19/20 |
| Gap or Opportunity | 20/20 |
| Refined Project Contribution | 14/15 |
| Evidence, Organization, and References | 5/5 |

- **Project Context:** clearly defines the problem, search terms, source selection, and rationale for balancing research with existing systems.
- **Research and Existing Solutions:** substantial critical analysis across research and deployed tools, although some evaluations could be examined beyond abstracts and headline performance figures.
- **Comparative Analysis:** compares meaningful technical and practical dimensions, but could distinguish more explicitly between functions not documented and functions confirmed absent.
- **Gap or Opportunity:** establishes a focused, evidence-supported opportunity while acknowledging that commercial platforms already provide overlapping capabilities.
- **Refined Project Contribution:** clearly explains five evidence-informed refinements, but the minimum scope and priorities across the proposed AI components could be more explicit.
- **Evidence, Organization, and References:** clear citations, credible sources, and an effective distinction between research findings, vendor claims, and project expectations.

Overall: a strong analytical report that connects the reviewed evidence directly to meaningful changes in the proposed workflow. For P3, prioritize the minimum implementation and make the limits of undocumented commercial capabilities explicit.

**What we did in P3:** split the work into a minimum version and a second priority (suggestions), and stated that "a commercial tool lacks X" means only that X is not in its public documentation.

## P1: Project Proposal

**94/100**

| Criterion | Mark |
|---|---|
| Project Overview | 5/5 |
| Problem Description | 19/20 |
| Motivation and Significance | 14/15 |
| Project Objectives | 14/15 |
| Intended Users and Stakeholders | 10/10 |
| Preliminary Proposed Solution / Methodology | 18/20 |
| Project Scope and Feasibility | 9/10 |
| Clarity, Organization, and References | 5/5 |

The proposal clearly identifies the problem of turning large amounts of hospital feedback into actionable quality-improvement information. The proposed pipeline from de-identification, classification and clustering to pathway mapping and RAG-based suggestions provides a clear direction for development, and the role of human review for generated improvement suggestions is well defined.

As we move into development, we need to:

- Define how the classification labels and care-pathway stages will be created, and how the hand-labelled dataset will be used as the reference for evaluation.
- Say which classification tasks the F1 target of about 0.7 applies to, and how sentiment, urgency, topic and pathway-stage classification will each be assessed.
- Define what makes a cluster good or meaningful, rather than relying only on comparison with existing labels.
- Give de-identification its own evaluation, with test cases for whether names, dates, record numbers and other identifying information are detected and removed.
- Set clear criteria for relevance, actionability and citation support, so the two reviewers rate RAG suggestions consistently.
- Build the minimum workflow first, before expanding the suggestion engine or dashboard.

**What we did in P3:** HCAT label scheme and a labelling guide; a 300-comment held-out test set with two-person agreement checks; a separate target for each task; a definition of a good issue plus built-in known problems; a de-identification test set; a 0-2 scoring guide for suggestions; and the minimum-version-first plan.

## P0: Team Formation and Topic Selection

**Strengths**

- The project idea is clear and relevant to Web Health Informatics.
- Good use of NLP/LLMs for analyzing hospital feedback.
- The intended users and overall purpose of the system are explained well.
- The preliminary technology stack is reasonable for the proposed project.

**To improve / consider for P1**

- Narrow the scope a little, especially around what type of feedback the system will analyze.
- Clearly define what kind of actionable improvements the system is expected to suggest.
- Consider how privacy will be handled if hospital or patient-related feedback is used.
- Explain how the team will verify that LLM-generated suggestions are reliable.

**What we did:** P1 added de-identification before storage, cited RAG suggestions with human review, and a plan for rating suggestions. P3 narrowed the data to two sources and defined an actionable suggestion.
