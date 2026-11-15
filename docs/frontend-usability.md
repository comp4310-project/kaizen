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

## Task study

Give each participant the same starting data and a QI account. Reset the fixture between
participants so a previous label correction cannot change the next session.

| Task | Success criterion |
|---|---|
| From the issues page, find the comments behind the highest ranked issue. | Opens the correct issue and identifies a comment. Record clicks from the issues page. |
| Find a category reported by patients or families only, then compare the same period by care stage. | Names a correct category and switches the comparison to stage. |
| Correct the urgency of a specified comment and confirm its labels. | The requested urgency and the confirmed status appear on that comment. |
| Show staff comments for unit 4B and download the displayed comments. | CSV comment IDs match the displayed list and all rows are staff feedback from 4B. |

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

Participant sessions and a manual screen reader check are pending.
