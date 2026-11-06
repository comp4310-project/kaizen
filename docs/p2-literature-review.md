# P2: Literature and Existing-System Analysis

COMP 4310 Web Health Informatics, Lakehead University
Submitted to D2L. Grade: 96/100 (feedback in [feedback.md](feedback.md#p2-literature-and-existing-system-analysis)).

This mirrors what went in the PDF. Student IDs are in the submitted version only, since
this repo is public.

## 1. Project Context and Investigation Approach

Our project is Kaizen: Turning Hospital Feedback into Actionable Quality Improvements. Hospitals collect a lot of written feedback, such as survey comments and complaints from patients and families, and comments and incident reports from staff. Most of it is never analysed properly. In one large study of English hospitals, three quarters of patient-experience leads said staff simply did not have time to look at the data [1]. As a result, the same problems keep coming up. Kaizen aims to help a hospital's quality-improvement (QI) team find recurring problems in this feedback, see where in the hospital they happen, and get draft ideas for fixing them that a person then reviews.

Because Kaizen is both an AI project and a web application, we looked at research papers and at real systems that hospitals use today. Our main search terms were "patient experience" free text NLP, patient comments machine learning, topic modelling patient feedback, BERTopic, large language model complaints, incident report classification, healthcare complaints analysis tool, and patient experience platform. We searched Google Scholar, PubMed, JMIR and BMJ journals, and arXiv for research, and vendor websites, GitHub and health-agency sites (CIHI, Ontario Health, NHS) for existing systems.

We kept a source if it dealt with analysing written healthcare feedback, came from a peer-reviewed journal or an official site, and was fairly recent (mostly 2019 onwards, plus a few key older papers). We preferred studies that reported how well their method worked, and we looked specifically for Canadian work. Some articles were paywalled, so for those we relied on the abstract and publisher page. This is a focused review for a course project, not a systematic review. In total we analysed 12 research studies and reviews, five existing systems and three supporting tools. Because the AI steps carry most of Kaizen's technical risk, we gave research studies more space, while still examining the systems hospitals use today.

## 2. Analysis of Relevant Research and Existing Solutions

### 2.1 Reviews of the field

Khanbhai et al. [2] reviewed 19 studies that applied natural language processing (NLP) and machine learning to patient feedback. Most used online reviews or social media rather than hospital survey comments, and fairly simple classifiers worked well. Their main conclusion was that there is still no standard way to turn the results into actual improvements. Gleeson et al. [3] looked at how hospitals use patient-experience data for QI and found a similar problem from the other side: staff valued written comments but lacked the time and skills to analyse them, and the changes that resulted were mostly small administrative fixes.

### 2.2 NLP studies on patient comments

Cammel et al. [4] analysed tens of thousands of Dutch inpatient comments using topic modelling (grouping comments that use similar words) and sentiment scoring. They then flagged each topic as something to improve, monitor or celebrate. Their sentiment scores agreed well with human raters, but each comment was only given one topic, and they did not test whether hospitals found the output useful.

Steele et al. [5] is the closest Canadian study. They used BERTopic, a newer method that groups comments by meaning rather than exact words, on about 47,000 survey comments from Alberta hospitals. It found issues the survey questions never ask about, such as parking and room temperature. However, they did not measure accuracy, and they left analysis by hospital unit for future work.

Khanbhai et al. [6] is one of the few studies of a system actually used in hospitals. A standard machine learning model tagged patient comments from nine English hospital trusts with themes and sentiment, and showed results on dashboards. Accuracy reached at least 75% for themes at every hospital (76-90% where exact figures were given), but the first five hospitals needed their own coded examples to get there; the last four did not. It did not group recurring problems or suggest any actions.

Shankar and Yip [7] went one step further. After analysing about 92,000 written comments from a Singapore hospital, they held workshops with clinicians, administrators and patient representatives to check the findings and develop improvement plans together. This led to five interventions, such as text-message alerts for waiting patients and a redesigned billing statement. Their analysis tools identified the problem areas but did not propose solutions; the plans were co-developed in the workshops. The paper reports improvements afterwards, such as fewer billing complaints, but it does not describe a comparison group or statistical testing, so it is hard to tell how much of the change came from the interventions.

### 2.3 Large language models

Koh et al. [8] tested three large language models (LLMs), GPT-3.5, GPT-4o mini and Claude 3.5 Sonnet, on sorting 1,816 complaints from primary care clinics in Singapore into categories. The models matched human coders on the broad type of complaint about 80% of the time, but did poorly on judging how serious a complaint was. They also tried to label the stage of care where the problem happened, which is the closest earlier work to what Kaizen wants to do, and matched human coders in only about 61-68% of cases. The authors note as a limitation that each complaint could get only one label, which may oversimplify complaints that involve several issues.

### 2.4 Staff feedback and incident reports

Staff written feedback has mostly been studied in the form of patient safety incident reports. Wang et al. [9] trained a deep learning model (a convolutional neural network) on incident reports from a statewide reporting system. It identified common incident types, such as falls and medication incidents, with F scores above 85%, and it classified severity better than the older models they compared it with. However, the abstract reports results only for common incident types, so it does not show how well the model handles rarer ones. None of the staff-side studies we found looked at staff and patient feedback together.

### 2.5 How hospitals use and combine feedback

Research on hospitals themselves shows why good analysis alone is not enough. Locock et al. [1] surveyed patient-experience leads in English hospitals and followed six medical wards as they worked on improvement projects. Lack of staff time was by far the most common barrier to using patient-experience data (75%), and before-and-after surveys on the wards showed little statistically significant change in patient experience.

Two studies are especially relevant to Kaizen. Gillespie and Reader developed and tested the Healthcare Complaints Analysis Tool (HCAT) [10], a coding scheme that records each problem's type, severity and stage of care, along with the level of harm. When they applied it to 1,110 complaints from across England, serious harm clustered around institutional problems at admission and discharge, and problems before admission and after discharge were identified as "blind spots" that hospitals find hard to monitor [11]. Van Dael et al. [12] compared five years of patient complaints with staff incident reports at a large London hospital. Only 7.6% of complaints and 0.6% of staff reports described the same events, and in those shared events patients reported more harm than staff in about 60% of cases. In other words, patients and staff often notice different problems, so looking at only one group misses a lot.

### 2.6 Existing systems

Several commercial platforms already analyse patient comments. Press Ganey, which describes itself as the leading provider of patient-experience measurement for health systems, announced three AI features in 2025: AI Summarize, AI Compose, which drafts responses, and AI Recommend, which it says provides "actionable recommendations" and detects safety risks in patient feedback [13]. The platform also draws on employee feedback and patient-safety data. In 2026 it launched Narrative HX, a text-analysis tool that it says commonly achieves accuracy "in the mid-90% range" [14]. NRC Health uses AI to tag every patient comment with a category, record who was involved and what they did, and flag comments that describe serious problems such as clinical errors or mistreatment; it states that its accuracy is above 88% [15]. Neither company explains how these accuracy figures were measured, and we could not find a published independent evaluation of either tool. This does not mean the tools are inaccurate, only that the claims cannot be checked from public sources. Press Ganey also does not explain what its recommendations are based on or how staff should check them. Qualtrics takes a more general approach: its Text iQ feature, part of its survey platform, adds sentiment, effort and emotion labels to open-ended answers and sorts comments by "actionability", from "Response needed" for urgent requests to "Suggestions" for ideas that matter in aggregate [16]. Its documentation is not specific to healthcare, gives no accuracy figures, and warns that actionability "is not guaranteed to catch every urgent request" [16].

The best documented open-source option is pxtextmining, funded by NHS England [17]. It sorts patient comments from the NHS Friends and Family Test into 32 categories, can give a comment more than one category, and publishes its accuracy openly, which is rare. It scores well on common categories but much worse on some rare ones, it only handles patient comments, and it stops at classification. Care Opinion [18] takes a different approach: people share their care stories publicly, a trained team moderates and tags them, and health services respond publicly. In Western Australia in 2024/25, services responded to 99.5% of 1,411 stories, but only 28 were recorded as leading to a change, either planned or made [19].

### 2.7 Supporting technologies

Kaizen will build on existing tools rather than invent new ones. BERTopic [20] groups similar comments together. Retrieval-augmented generation (RAG) [21] lets an LLM answer using specific documents we give it, such as hospital policies, so its suggestions can point to a source. Presidio [22], an open-source tool, finds and removes names and other personal details from text, although its own documentation warns that there is no guarantee it will find all of them.

## 3. Comparative Analysis

Table 1 compares the most relevant items. R = research, C = commercial, OS = open source, NP = non-profit.

**Table 1. Comparison of selected research and existing systems**

| Item (type) | Data used | Approach | Shows where it happened? | Suggests fixes? | Evaluation |
|---|---|---|---|---|---|
| Cammel 2020 [4] (R) | Patient comments | Topic modelling + sentiment | No | Flags topics to improve | Agreement with raters |
| Steele 2025 [5] (R, Alberta) | Patient comments | BERTopic | No | No | Descriptive only |
| Khanbhai 2025 [6] (R, deployed) | Patient comments | Machine learning classifier | No | No | At least 75% accuracy |
| Koh 2025 [8] (R) | Patient complaints | LLMs | Partly (stage of care) | No | Compared with human coders |
| van Dael 2022 [12] (R) | Complaints + staff incident reports | Manual review | n/a | No | Overlap study |
| Press Ganey [13], [14] (C) | Patient + employee + safety | AI features incl. generative AI | Not described | Yes, basis not stated | Vendor claim (mid-90%) |
| NRC Health [15] (C) | Patient comments | AI tagging and alerts | Not described | No, flags issues | Vendor claim (above 88%) |
| Qualtrics Text iQ [16] (C) | Open-ended survey answers | Text analytics labels | Not described | No, flags actionable comments | No accuracy published |
| pxtextmining [17] (OS) | Patient comments | Machine learning | No | No | Published scores |
| Care Opinion [18] (NP) | Public patient stories | Human moderators | Provider named | Human replies | Activity reports |
| Kaizen (planned) | Patient + staff | Clustering + LLM + RAG | Yes, from the text | Yes, cited and reviewed | To be measured |

The table shows a clear pattern. Research studies are open about their methods and usually test them, but each one covers only one step, such as sorting or grouping comments, and almost all of them use patient feedback only. Commercial platforms cover more steps, and Press Ganey even combines patient, employee and safety data, but Press Ganey and NRC Health do not explain how their accuracy figures were measured, Qualtrics gives no figure, and we found no published independent evaluation of Press Ganey's or NRC's tools. The open-source pxtextmining sits in between: open and actually used, but limited to sorting patient comments.

Two weaknesses stand out. First, several of the research tools (Cammel, Steele and Koh) give each comment only one label, even though one comment can describe several problems. Second, of the studies and systems we reviewed, only Koh et al. tried to work out from the comment itself where in the care process a problem happened, and their results were only moderately accurate.

There are also strengths we can reuse. Simple models still work well, newer grouping methods find issues that surveys miss, HCAT gives us a tested way to describe complaints, and Care Opinion's figures show that responding to feedback is not the same as acting on it.

Table 2 adds two dimensions that matter when choosing what to build on: who each item is meant for, and its main limitation.

**Table 2. Intended users and main limitation of each item**

| Item | Intended users | Main limitation |
|---|---|---|
| Cammel 2020 [4] | Hospital improvement teams | One topic per comment; usefulness to hospitals not tested |
| Steele 2025 [5] | Researchers, policy makers and administrators | No accuracy measured; no analysis by unit |
| Khanbhai 2025 [6] | NHS hospital patient-experience teams | First five hospitals needed their own coded examples |
| Koh 2025 [8] | Service quality staff in health care organisations | One label per complaint; poor at judging severity |
| van Dael 2022 [12] | Hospitals analysing safety incidents | Manual matching that needs identifiable records |
| Press Ganey [13], [14] | Health systems | Accuracy method and basis of recommendations not published |
| NRC Health [15] | Health systems and frontline staff | No independent check of its accuracy claim found |
| Qualtrics Text iQ [16] | Organisations analysing open-ended survey answers | Not healthcare-specific; may miss urgent requests, by its own warning |
| pxtextmining [17] | NHS organisations using the Friends and Family Test | Patient comments only; weak on rare categories |
| Care Opinion [18] | Patients, families and health services | In Western Australia, few stories led to recorded change |
| Kaizen (planned) | Hospital QI teams, ward managers and administrators | Tested only on synthetic and public data, with no hospital partner |

## 4. Gap or Opportunity

We cannot say that nothing like Kaizen exists. Press Ganey already offers a platform that combines patient, employee and safety data and gives AI recommendations [13], and NRC Health already uses AI to tag and flag patient comments [15]. The gap we found is narrower: we did not find any published, openly evaluated approach that does the following three things together.

First, it would look at patient and staff feedback side by side. Van Dael et al. showed that complaints and staff incident reports rarely describe the same events [12], yet every NLP study we reviewed used only one of the two. Showing where patients and staff agree, and where they disagree, could reveal problems that either group alone would miss.

Second, it would work out where in the hospital a problem happens from the comment itself. Complaints research shows that serious harm clusters around admission and discharge, and that problems before admission and after discharge are hard for hospitals to monitor [11]. Yet the only study we found that tried to read the stage of care from the comment text matched human coders in only about two-thirds of cases [8].

Third, it would turn findings into improvement suggestions that are based on sources and checked by a person. Press Ganey says its AI gives recommendations but does not explain what they are based on [13], and in the one study we found that led to changes, the improvement plans were developed by people in workshops rather than by the analysis tools [7].

This gap matters because the most common barrier hospitals report is a lack of staff time to look at the feedback [1], [3]. Responding to feedback is also much more common than acting on it: in Western Australia, only 28 of 1,411 stories were recorded as leading to a planned or completed change [19]. A tool that saves analysis time and gives staff a starting point for action could help with this, although it cannot replace the people who decide what to change.

There is also a local reason this matters. CIHI stopped running its national patient-experience reporting system in April 2025, although it still provides the CPES-IC inpatient survey for quality improvement [23]. We think this makes local tools for analysing feedback more useful. In Ontario, whether patients feel completely informed about what to do after leaving hospital was the second most frequently chosen hospital quality-improvement indicator for 2025/26, selected by 41.8% of hospitals [24], which fits well with Kaizen's focus on discharge.

## 5. Refined Project Contribution

Kaizen will not invent a new algorithm. Its contribution is putting existing methods together into one workflow and testing it honestly: comments from patients and staff are de-identified, sorted, grouped into recurring problems, placed on the care pathway, and turned into draft suggestions that a QI reviewer must accept, edit or reject. This is more than connecting to an LLM, because the value comes from how the steps fit together, how patient and staff feedback are compared, and how the suggestions are checked.

Based on this analysis, we have made five changes to our P1 plan:

- **More than one label per comment.** P1 gave each comment one category. Koh et al. note that one label per complaint may oversimplify complaints with several issues [8], and pxtextmining shows that a multi-label model can work in practice [17], so Kaizen will allow several.
- **A person always confirms how serious an issue is.** LLMs agreed poorly with human coders on severity [8]. Qualtrics also warns that its own urgency label may miss urgent requests [16]. Kaizen can suggest an urgency level, but a staff member has to confirm it.
- **Compare patient and staff feedback by topic and ward.** Because our data are de-identified, we cannot match records patient by patient as van Dael did [12]. Instead, Kaizen will compare what patients and staff say about the same topic in the same ward, and show where they disagree, not only where they agree.
- **A clearer way to evaluate suggestions.** Two team members will rate each suggestion using a simple rubric (is it supported by the cited source, is it practical, is it safe), and Kaizen will record every accept, edit and reject decision.
- **Use HCAT's stages of care to locate each problem, and measure how well it works.** P1 used our own list of care-pathway stages. Kaizen will instead label each comment with one of HCAT's stages of care (admissions, examination and diagnosis, care on the ward, operation and procedures, or discharge and transfers) [10], plus the ward when the source records it. A reviewer can correct the stage, and we will report how often Kaizen's stage matches our own hand labels, so it can be compared with the 61-68% agreement Koh et al. reported [8].

Together these changes answer the three parts of the gap in Section 4. The third change covers looking at patient and staff feedback side by side, the fifth covers working out where a problem happens, and the fourth, together with the cited suggestions already in our design, covers suggestions that are based on sources and checked by a person.

The rest of the P1 design stays the same: a React and Python web app with a MySQL database, using only synthetic and public data, with no hospital partner. Because of this, our results will show whether the workflow is possible and can be evaluated, not whether it improves real care. We will also keep discharge problems as one of our main test cases, since our synthetic data already include them and they match both the research [11] and Ontario's priorities [24].

## 6. References

1. L. Locock et al., "Understanding how front-line staff use patient experience data for service improvement: an exploratory case study evaluation," Health Serv. Deliv. Res., vol. 8, no. 13, 2020, doi: 10.3310/hsdr08130.
2. M. Khanbhai, P. Anyadi, J. Symons, K. Flott, A. Darzi, and E. Mayer, "Applying natural language processing and machine learning techniques to patient experience feedback: a systematic review," BMJ Health Care Inform., vol. 28, no. 1, Art. no. e100262, 2021, doi: 10.1136/bmjhci-2020-100262.
3. H. Gleeson, A. Calderon, V. Swami, J. Deighton, M. Wolpert, and J. Edbrooke-Childs, "Systematic review of approaches to using patient experience data for quality improvement in healthcare settings," BMJ Open, vol. 6, no. 8, Art. no. e011907, 2016, doi: 10.1136/bmjopen-2016-011907.
4. S. A. Cammel et al., "How to automatically turn patient experience free-text responses into actionable insights: a natural language programming (NLP) approach," BMC Med. Inform. Decis. Mak., vol. 20, no. 1, Art. no. 97, 2020, doi: 10.1186/s12911-020-1104-5.
5. B. Steele, P. Fairie, K. Kemp, A. G. D'Souza, M. Wilms, and M. J. Santana, "Identifying patient-reported care experiences in free-text survey comments: topic modeling study," JMIR Med. Inform., vol. 13, Art. no. e63466, 2025, doi: 10.2196/63466.
6. M. Khanbhai, C. Carenzo, S. Aryasinghe, D. Manton, and E. Mayer, "Leveraging AI to drive timely improvements in patient experience feedback: algorithm validation," JMIR Med. Inform., vol. 13, Art. no. e60900, 2025, doi: 10.2196/60900.
7. R. Shankar and A. Yip, "Transforming patient feedback into actionable insights through natural language processing: knowledge discovery and action research study," JMIR Form. Res., vol. 9, Art. no. e69699, 2025, doi: 10.2196/69699.
8. S. W. C. Koh et al., "Classifying patient complaints using artificial intelligence-powered large language models: cross-sectional study," J. Med. Internet Res., vol. 27, Art. no. e74231, 2025, doi: 10.2196/74231.
9. Y. Wang, E. Coiera, and F. Magrabi, "Using convolutional neural networks to identify patient safety incident reports by type and severity," J. Am. Med. Inform. Assoc., vol. 26, no. 12, pp. 1600-1608, 2019, doi: 10.1093/jamia/ocz146.
10. A. Gillespie and T. W. Reader, "The Healthcare Complaints Analysis Tool: development and reliability testing of a method for service monitoring and organisational learning," BMJ Qual. Saf., vol. 25, no. 12, pp. 937-946, 2016, doi: 10.1136/bmjqs-2015-004596.
11. A. Gillespie and T. W. Reader, "Patient-centered insights: using health care complaints to reveal hot spots and blind spots in quality and safety," Milbank Q., vol. 96, no. 3, pp. 530-567, 2018, doi: 10.1111/1468-0009.12338.
12. J. van Dael et al., "Getting the whole story: integrating patient complaints and staff reports of unsafe care," J. Health Serv. Res. Policy, vol. 27, no. 1, pp. 41-49, 2022, doi: 10.1177/13558196211029323.
13. Press Ganey, "Press Ganey expands AI capabilities to transform safety and the experience of patients and healthcare employees," News release, Jan. 14, 2025. https://www.pressganey.com/resources/news/press-ganey-expands-ai-capabilities-to-transform-safety-and-the-experience-of-patients-and-healthcare-employees/
14. Press Ganey, "Press Ganey launches Narrative HX to turn unstructured feedback into fast, actionable insight," News release, Feb. 3, 2026. https://www.pressganey.com/resources/news/press-ganey-launches-narrative-hx-to-turn-unstructured-feedback-into-fast-actionable-insight/
15. NRC Health, "Artificial intelligence capabilities." https://nrchealth.com/nrc-health-artificial-intelligence-capabilities
16. Qualtrics, "Additional enrichments in Text iQ," Qualtrics Support. https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/text-iq/actionability/
17. The Strategy Unit, "pxtextmining," GitHub repository and model performance documentation, Patient Experience Qualitative Data Categorisation project. https://github.com/the-strategy-unit/pxtextmining and https://the-strategy-unit.github.io/PatientExperience-QDC/pxtextmining/model_performance.html
18. Care Opinion Australia, "Care Opinion" provider brochure. https://www.careopinion.org.au/resources/CareOpinion-Brochure-web.pdf
19. Department of Health, Western Australia, "Care Opinion activity summary 2024/25." https://www.healthywa.wa.gov.au/~/media/HWA/Documents/WA-Health-system/Care-Opinion-Activity-Summary-2024-25.pdf
20. M. Grootendorst, "BERTopic: Neural topic modeling with a class-based TF-IDF procedure," arXiv preprint arXiv:2203.05794, 2022.
21. P. Lewis et al., "Retrieval-augmented generation for knowledge-intensive NLP tasks," in Advances in Neural Information Processing Systems 33 (NeurIPS 2020), 2020, pp. 9459-9474.
22. Data Privacy Stack, "Presidio" documentation (open source). https://presidio.dataprivacystack.org/
23. Canadian Institute for Health Information, "Patient experience." https://www.cihi.ca/en/patient-experience
24. Ontario Health, "Highlighting the 2025/26 QIP indicator matrix and selection trends," Quorum. https://quorum.hqontario.ca/en/Home/Posts/Highlighting-the-2025-26-QIP-Indicator-Matrix-and-Selection-Trends
