# Front end tasks

Front end work owned by Aansh (P3 Table 8: FR5, FR6, FR8, NFR4). The endpoints for
FR5, FR6 and FR8 are on `main`. How to add a page and the rules every page follows
are in `AGENTS.md`.

## FR5: patient and staff comparison

P3: "Show patient and staff feedback side by side by topic, stage and unit, and mark where
only one group reports a problem." User story: a QI analyst wants to "see whether patients,
staff or both report an issue". QI, admin and managers can all see it.

`GET /compare?by=category|stage|unit&unit=ED&date_from=2026-01-01&date_to=2026-03-31`.
`by` defaults to `category`; the rest are optional. Managers always get their own unit and
403 for another. 422 if `date_from` is after `date_to`.

```ts
interface CompareOut {
  by: "category" | "stage" | "unit";
  unit: string | null;
  date_from: string | null;
  date_to: string | null;
  totals: { patient: number; staff: number };   // every labelled comment in range
  rows: { key: string; patient: number; staff: number; only: "patient" | "staff" | null }[];
}
```

Rows come sorted by total, largest first. A comment with two categories counts in both
rows, so category rows can add up to more than `totals`; say so under the table.

Implemented at `/compare` for QI, admin and managers. The unit choices come from
`api.units()`, and managers see only their assigned unit. Both count columns share
the same bar scale. The table shows which groups reported each category, stage or unit.

Done when:
- Known patterns in the synthetic data appear correctly (P3 Table 2 check). With the current NHS data every comment is patient or family, so every row should show "Only patients"; check a staff pattern once Bhavya's synthetic staff comments are loaded.
- A manager sees only their unit and cannot pick another.
- Loading, empty ("No labelled comments in this range") and error states work.

## FR6: confirm and correct labels, redact, rename, merge

P3: "Let QI staff confirm urgency, correct labels, redact a personal detail that
de-identification missed, and rename or merge issues. Every change is logged." Priority:
Must, with rename, merge and redact Should. User story: a QI analyst wants to "confirm or
correct the urgency and stage the system suggests". QI and admin only; hide every control
for managers with the same check as the draft button.

### Labels

`POST /comments/{id}/labels` with any of `sentiment`, `categories`, `stage`, `urgency`.
An empty body `{}` confirms the labels as they are. 404 no such comment, 409 not labelled
yet.

```ts
interface LabelsIn {
  sentiment?: "positive" | "neutral" | "negative";
  categories?: ("quality" | "safety" | "environment" | "institutional_processes" | "listening" | "communication" | "respect_and_rights")[];
  stage?: Stage;
  urgency?: "low" | "medium" | "high";
}
interface LabelsOut extends Required<LabelsIn> {
  comment_id: number;
  status: "suggested" | "confirmed";
  suggested: { sentiment: string; categories: string[]; stage: string; urgency: string };  // the model's first answer, never changed
  confirmed_by: number | null;   // user id, not a name
  confirmed_at: string | null;
}
```

Build: in `IssueDetailPage.tsx`, give each comment's `Labels` block a "Confirm" button and
an "Edit labels" button that opens a small form, the same pattern as the edit form in
`SuggestionCard.tsx` (selects for sentiment, stage and urgency, checkboxes in a
`<fieldset>` with a `<legend>` for categories). Send only changed fields. Replace the
comment's labels with the reply so "suggested by the model" turns into "checked by a
person".

### Redact

`POST /comments/{id}/redact` with `{ start, end }`: character offsets into the stored text,
`end` exclusive. 422 if the range is empty or past the end. Returns `{ id, text }` with the
range replaced by `<REDACTED>`.

Build: a "Redact" button per comment that opens a form with the text in a read-only
`<textarea>`; the person selects the detail and the form reads `selectionStart` and
`selectionEnd`. Show the selected text and ask to confirm before sending. Replace the
comment text with the reply. Don't log or keep the selected text anywhere.

### Rename and merge

`POST /issues/{id}/rename` with `{ name }` (1 to 120 characters), returns
`{ id, rank, name }`.

`POST /issues/{id}/merge` with `{ into: otherId }`. Moves this issue's comments and
suggestions into `into`, recomputes its counts and score, re-ranks the run and deletes
this issue. 422 for merging into itself or across runs. Returns
`{ id, rank, name, size, patient_count, staff_count, score }` for the merged issue.

Build: on the issue detail page header, "Rename" (inline form like the suggestion edit) and
"Merge into" (a select of the other issues from `api.issues()`, then a confirm step saying
this issue will be deleted). After a merge, navigate to `/issues/{into}`. After a rename,
update the heading.

Done when:
- Each change creates a log entry (P3 Table 2 check). Verify with `SELECT action, detail FROM activity_log ORDER BY id DESC LIMIT 5` after each action: `confirm_labels` or `correct_labels`, `redact_comment`, `rename_issue`, `merge_issue`.
- No control shows for a manager.
- Every form has labels, works by keyboard, and shows the API's 409 and 422 messages through `ErrorNotice`.

## FR8: filters and CSV export

P3: "Dashboard with ranked issues and the comments behind each, plus filters and CSV
export." Priority: Must, with filters and export Should. User story: a unit manager wants
to "see the issues and comments for my unit only" (the API already does this).

`GET /issues/{id}/comments` gains `unit` and `source` (`patient_family` or `staff`)
filters and `format=csv`. Managers are held to their own unit. With `format=csv` it
returns the same rows under the same filters, `limit` and `offset`, as a file:

```
id,source,unit,date,typical,sentiment,categories,stage,urgency,status,text
```

`typical` is `yes` or `no`, categories are joined with `;`, and cells starting with `=`,
`+`, `-` or `@` get a leading `'`. `limit` is capped at 500, so an issue with more
comments needs several requests or a back end change. Agree which with whoever reviews the back end
branch before building it.

Build: add `unit` and `source` to `api.issueComments` options and a toolbar above the
comments in `IssueDetailPage.tsx` (unit select for QI and admin, source select for
everyone). Add a `download(path, filename)` helper in `api.ts` that fetches with the token
header, turns the reply into a blob and clicks a temporary `<a download>`; a plain link
cannot send the token. "Download CSV" is a `btn-secondary` that uses the current filters.
`GET /issues` has no filters on the back end yet, so issue-table filters (by stage or
rising) would be client-side for now.

Done when:
- Export matches the filtered view (P3 Table 2 check): with a filter set, the CSV has the same comment ids as the page.
- The file opens in a spreadsheet without running a formula from comment text.
- The filters keep working after "Show more".

## NFR4: accessibility scan and SUS test

P3 Table 3: "The comments behind the top issue are reachable in three clicks or fewer;
meets WCAG 2.1 AA contrast and keyboard rules." Checked by "Five-person task test with SUS
questionnaire; accessibility scan." P3 Table 9 target: SUS of 68 or more from five
classmates doing four tasks.

To do:
- Run an automated scan (axe DevTools or Lighthouse) on every page in light and dark, logged in as QI and as a manager. Fix or record each finding.
- Tab through every page with the keyboard only, and try the issues and issue detail pages with a screen reader (NVDA on Windows).
- Write the four tasks, for example: find the top issue's comments (should take one click), find whether staff report it, draft and accept a suggestion, export the comments for unit ED. Run them with five classmates and score the SUS forms.
- Put the scan results, the task times and the SUS score in `docs/`.

Three clicks: the top issue's comments are one click from the issues page, which is where
login lands.
