# Front end accessibility and usability evaluation

P3 NFR4 asks for WCAG 2.1 AA contrast and keyboard checks, access to the top issue's
comments in three clicks or fewer, and a task test with five classmates. Use a local
database with synthetic comments and both a QI account and a unit manager account.

## Automated checks

Chromium and axe-core 4.11.1 reported no WCAG 2.0 or 2.1 A/AA rule violations across
24 scanned states at 375 px. The scan covered login, the issue list, issue detail,
comparison, the QI suggestion queue, and the four correction forms in light and dark.
The issue list, detail, and comparison were checked as both QI and a unit manager.
The scan ran with reduced motion so colours had settled when measured.

The browser opened the top issue from the list with one keyboard activation and
checked the accessibility tree for links and headings. It also exercised label
confirmation and correction, selection and redaction, renaming and merging. CSV
comment IDs matched the filtered list both before and after Show more. The manager
could export their own unit's feedback and saw no correction controls.

A separate keyboard-only Chromium walkthrough checked visible focus and the skip
link. It covered login, opening the top issue, choosing filters, triggering a CSV
download, and switching comparison grouping as QI and as a manager. The QI walkthrough
also reached the first label field one Tab after opening the editor, cancelled the
edit by keyboard, and used the suggestion queue filter. No keyboard blocker occurred
on those paths.

## Set up a session

Use a fresh, local SQLite database for each participant so one session's changes cannot
affect another. After installing the project as described in the [README](../README.md),
run this from `backend/` in PowerShell:

```powershell
python scripts/seed_usability.py study-P1.db
$env:KAIZEN_DATABASE_URL = 'sqlite:///./study-P1.db'
uvicorn kaizen.api.app:create_app --factory
```

Start the frontend with `npm run dev` from `frontend/` in a second terminal. Open
`http://localhost:5173` in a private browser window and sign in as `study-qi` with the
password entered when seeding the database. For the next participant, stop the API,
close the private window, and repeat with a new filename such as `study-P2.db`. The
seeder refuses to overwrite an existing database. No model keys or real data are needed.

## Task study

Read one task at a time. Start on the Issues page each time. Ask the participant to say
when they think they have finished. Start the timer when you hand over the task and stop
when they finish or give up. Keep the success criteria for the facilitator.

| Task | Success criterion |
|---|---|
| Find the comments behind the highest ranked issue and tell me how many there are. | Opens Delayed discharge instructions and reports four comments. Record clicks from the issues page. |
| Find a category reported only by patients or families, then compare the same feedback by care stage. | Identifies environment and switches the grouping to stage of care. |
| Change the urgency of Comment 1 on the top issue from low to high and confirm its labels. | Comment 1 shows high urgency and checked by a person. |
| On the top issue, show staff comments for unit 4B and download the displayed comments. | Two rows appear. Their IDs match the CSV and both rows are staff feedback from 4B. |

For each task, record completion, elapsed seconds, navigation actions and any help
given. After all four tasks, give the participant the ten-item
[System Usability Scale questionnaire](https://hci-studies.org/methods-and-measures/downloads/SUS_Brooke1996.pdf).
For odd-numbered items, subtract 1 from the response. For even-numbered items, subtract
the response from 5. Add the ten contributions and multiply by 2.5. Report the mean of
the five scores and whether it reaches P3's target of 68. Use participant codes and keep
the individual forms out of the repository.

| Participant code | Task outcomes and seconds | Task 1 clicks | SUS score |
|---|---|---|---|
| P1 | | | |
| P2 | | | |
| P3 | | | |
| P4 | | | |
| P5 | | | |

## Screen reader check

Use the same fixture with Windows Narrator or NVDA. From Issues, navigate by headings,
links and table cells. Verify that issue names are announced as links and numbers are
read with their column headers. Open the top issue and read the comment heading, source
and unit selectors, a comment and its labels. Open Edit labels and check the field names,
the Categories group, and the confirmation announcement. Repeat the issue list and
detail checks as `study-manager`, which is scoped to unit 4B. Record the browser and
screen reader versions, observed speech and any blockers.

Participant results and live screen reader speech checks are pending.

## Changes after round 1

Round 1 used five simulated participants (LLM personas, not classmates) and gave a mean
SUS of 64.0 against the target of 68. These changes respond to what they ran into.

- The CSV button says "Download as spreadsheet (CSV)" and a polite live region beside it names the saved file and its row count, or the error, because none of the five could confirm task 4.
- The CSV button keeps focus while it works, because disabling it during the download dropped focus to the page.
- Edit labels moves focus to Sentiment, and Save labels sits right after Urgency as well as at the end, because four of five scrolled past the categories looking for it.
- The label editor says that saving marks the labels as checked by a person, and the category checkboxes no longer stretch to full width.
- Patient or family is the only name for that group, and the compare badge reads "Only patients or families", because three of five were unsure the terms meant the same people.
- "Suggested by the model" became "suggested automatically, not yet checked", and Typical and outliers are explained in visible text where they appear.
- The compare page says under the table what each grouping counts; rows still do not link to comments, because the API has no category or stage filter (recorded in `frontend/TASKS.md`).
- Below 900px the issues table moves Main stage under the issue name so it fits at 768px, and table wrappers allow touch panning in both directions.
- Unit options are sorted by code, and filters apply on a mouse pick, Enter, leaving the control or a 1.5 second pause, because arrowing through Unit reloaded and announced the count for every option.
- The header links show during the login check, and placeholder table rows no longer highlight under the pointer, because two participants clicked during loading and nothing happened.
