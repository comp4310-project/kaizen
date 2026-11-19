# Front end tasks

Front end work owned by Aansh (P3 Table 8: FR5, FR6, FR8, NFR4). The endpoints for
FR5, FR6 and FR8 are on `main`. How to add a page and the rules every page follows
are in `AGENTS.md`.

## FR1: upload and public feedback for P4

QI staff and admins upload a CSV at `/imports` and see saved and rejected row counts
with line numbers for the errors. Anyone can send one comment at `/feedback` using
the units returned by the API. Both pages use the existing import endpoints.

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

Drill-down done: each category, stage or unit name links to `/comments` with the same
filter, unit and dates, and each count links to the same list for that group only. The page
says how many of the counted labels a person has checked.

Follow-up from study round 1 (now done, see above): three of five participants wanted to click a row to see the
comments it counts, or to keep a chosen category when switching Group by (task 2). Neither
works with the current API, because `/compare`, `/issues` and `/issues/{id}/comments` have
no category or stage filter. The page says in one line under the table what each grouping
counts. A drill-down needs a `category` and `stage` filter on `/compare` (to show the stage
breakdown of one category) and on a comment list endpoint (to link a row to its comments).
Agree it with the back end owner first; grouping by unit could already link to the same
table filtered to that unit, since `/compare` takes `unit`.

Done when:
- Known patterns in the synthetic data appear correctly (P3 Table 2 check). With the current NHS data every comment is patient or family, so every row should show "Only patients or families"; check a staff pattern once Bhavya's synthetic staff comments are loaded.
- A manager sees only their unit and cannot pick another.
- Loading, empty ("No labelled comments in this range") and error states work.

## FR6: confirm and correct labels, redact, rename, merge

Implemented on issue detail for QI and admin. Managers see the comments without correction controls.

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

The issue detail page sends only changed fields and displays the confirmed values.

### Redact

`POST /comments/{id}/redact` with `{ start, end }`: character offsets into the stored text,
`end` exclusive. 422 if the range is empty or past the end. Returns `{ id, text }` with the
range replaced by `<REDACTED>`.

The redaction form previews the selected range before confirmation and shows the stored
text returned by the API. It converts browser offsets to Python character offsets.

### Rename and merge

`POST /issues/{id}/rename` with `{ name }` (1 to 120 characters), returns
`{ id, rank, name }`.

`POST /issues/{id}/merge` with `{ into: otherId }`. Moves this issue's comments and
suggestions into `into`, recomputes its counts and score, re-ranks the run and deletes
this issue. 422 for merging into itself or across runs. Returns
`{ id, rank, name, size, patient_count, staff_count, score }` for the merged issue.

The heading updates after renaming. Merging requires confirmation and opens the issue
that kept the comments.

Done when:
- Each change creates a log entry (P3 Table 2 check). Verify with `SELECT action, detail FROM activity_log ORDER BY id DESC LIMIT 5` after each action: `confirm_labels` or `correct_labels`, `redact_comment`, `rename_issue`, `merge_issue`.
- No control shows for a manager.
- Every form has labels, works by keyboard, and shows the API's 409 and 422 messages through `ErrorNotice`.

## FR8: filters and CSV export

Implemented on issue detail. Filters stay applied through pagination, and CSV export includes
all currently displayed comments under those filters.

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
`+`, `-` or `@` get a leading `'`. The client exports displayed rows in batches of
up to 500 and writes the CSV header once. Select Show more to include further comments.

Done when:
- Export matches the filtered view (P3 Table 2 check): with a filter set, the CSV has the same comment ids as the page.
- The file opens in a spreadsheet without running a formula from comment text.
- The filters keep working after "Show more".

## Overview, trend and processing

Done: `/overview` is the landing page for every role, with key numbers, a next step, comments
per week and the top three issues. Issue detail starts with a weekly chart and the rising rule
in words. QI and admin can press Process new feedback on the overview or the upload page,
which labels new comments and rebuilds the issues in the background (`POST /runs`).

Still open: the weekly chart has no keyboard way into single bars; the numbers are in the
table under "Show the numbers". Run the axe scan on the new pages.

## NFR4: accessibility scan and SUS test

See [the accessibility and usability evaluation](../docs/frontend-usability.md) for the
automated checks and the participant study plan.

P3 Table 3: "The comments behind the top issue are reachable in three clicks or fewer;
meets WCAG 2.1 AA contrast and keyboard rules." Checked by "Five-person task test with SUS
questionnaire; accessibility scan." P3 Table 9 target: SUS of 68 or more from five
classmates doing four tasks.

To do:
- Run an automated scan (axe DevTools or Lighthouse) on every page in light and dark, logged in as QI and as a manager. Fix or record each finding.
- Tab through every page with the keyboard only, and try the issues and issue detail pages with a screen reader (NVDA on Windows).
- Write the four tasks, for example: find the top issue's comments (should take one click), find whether staff report it, draft and accept a suggestion, export the comments for unit ED. Run them with five classmates and score the SUS forms.
- Put the scan results, the task times and the SUS score in `docs/`.

Three clicks: login lands on the overview, which links the top three issues, and each issue
page opens on its comments. The issues page also links every issue.
