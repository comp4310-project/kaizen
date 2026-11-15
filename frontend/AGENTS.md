# Notes for coding agents: front end

Read the root `AGENTS.md` first; its rules (data, commits, writing) apply here too. This
file covers `frontend/` only. Owner: Aansh (P3 Table 8: FR5, FR6, FR8, NFR4). Open work is
in `TASKS.md`.

## Stack

Exact versions, pinned in `package.json` with no `^` or `~`. Change a version only on
purpose, and commit the updated `package-lock.json` with it.

| Package | Version | Why |
|---|---|---|
| react, react-dom | 19.3.1 | UI |
| react-router-dom | 7.18.5 | Routes in `App.tsx` |
| vite | 8.3.5 | Dev server, `/api` proxy, build |
| @vitejs/plugin-react | 6.1.2 | JSX in Vite |
| typescript | 7.0.2 | `tsc --noEmit` in the build. If it causes trouble, 6.0.3 is the fallback |
| @types/react, @types/react-dom | 19.3.0 | Types |

No UI library, no state library, no CSS framework, no icon set. Don't add one without
agreeing it with the team. Node 24 and npm 11.

## Layout

```
index.html                  page shell
vite.config.ts              dev server on 5173; /api/* goes to localhost:8000 with /api removed
src/main.tsx                mounts App inside BrowserRouter and AuthProvider
src/App.tsx                 header, routes, RequireLogin guard
src/api.ts                  every API call and the types of its replies
src/auth.tsx                AuthProvider, useAuth(), canReviewSuggestions()
src/states.tsx              ErrorNotice, EmptyState, SkeletonRows, SkeletonBlocks, describeError()
src/format.ts               words(), percent(), sourceName(), roleName(), dateTime()
src/SuggestionCard.tsx      one suggestion: fields, citations, accept / edit / reject
src/IssueReview.tsx        issue and comment correction forms for QI and admin
src/pages/LoginPage.tsx
src/pages/IssuesPage.tsx        ranked table
src/pages/ComparePage.tsx       patient and staff counts by category, stage or unit
src/pages/IssueDetailPage.tsx   comments with labels, suggestions beside them for QI
src/pages/SuggestionsPage.tsx   review queue with a status filter
src/styles.css              every style, with the design tokens at the top
docs/screenshots/           each page in light, dark and at 375px wide
```

## API client

All requests go through `request()` in `src/api.ts`, which:

- prefixes `/api`, so `api.issues()` fetches `/api/issues` and Vite forwards it to `/issues` on uvicorn;
- adds `Authorization: Bearer <token>` from sessionStorage (`kaizen.token`);
- throws `ApiError` with `status` and FastAPI's `detail` as the message (a list of field errors is joined with "; ");
- uses `status` 0 when there was no answer at all (uvicorn not running);
- on a 401 for a request that sent a token, clears the token and calls the handler `auth.tsx` registers, which sends the user to `/login`.

Pages call the `api` object, never `fetch` directly. CSV export uses the same authenticated
request helper, reads the CSV response, and downloads it as a file.

The types in `api.ts` mirror the dicts the FastAPI handlers return. They are copied by hand,
so when a handler changes, change the type in the same PR:

| Types | Backend file |
|---|---|
| `LoginOut`, `Me`, `Unit` | `backend/kaizen/api/app.py` (`login`, `me`, `units`) |
| `CompareBy`, `CompareOut` | `backend/kaizen/api/compare.py` (`compare`) |
| `IssuesOut`, `IssueSummary`, `IssueRun`, `IssueCommentsOut`, `IssueComment`, `CommentLabels` | `backend/kaizen/api/issues.py` |
| `Suggestion`, `Citation`, `SuggestionsOut`, `DraftOut`, `Decision` | `backend/kaizen/api/suggestions.py` (`_out`, `DecisionIn`) |
| `Stage`, `STAGES` | `backend/kaizen/classify/labels.py` |
| `Role`, `Source`, `SuggestionStatus` | `backend/kaizen/db.py` |

Check a type against a live reply with curl through the proxy (see "Run and verify")
rather than trusting the docs page.

## Auth and roles

`AuthProvider` checks a stored token against `/me` on load and keeps `me` (username, role,
unit). `RequireLogin` in `App.tsx` wraps every route except `/login`.

Roles are `qi`, `admin` and `manager`. The API enforces access; the front end only hides
what a role cannot use, so nobody clicks a button that returns 403:

- `canReviewSuggestions(me)` is true for QI and admin. It gates the Suggestions nav link, the `/suggestions` route (managers are redirected to `/issues`) and the suggestions panel on issue detail.
- Managers only get their own unit's issues and comments from the API. Pages say so in a line of muted text, and the issues table adds a "Your unit" column from `unit_size`.
- New QI-only controls (all of FR6) use the same `canReviewSuggestions` check. If the name stops fitting, rename it to `isQi` everywhere in one commit.

## Design tokens

Defined on `:root` in `styles.css`, redefined under `prefers-color-scheme: dark`. Use the
variables, never a raw colour. Every text pair is at least 4.5:1 and every border, bar and
focus ring at least 3:1 in both modes; check a new colour before adding it.

| Token | Use |
|---|---|
| `--surface` | page background |
| `--surface-raised` | panels, cards, table wrapper, header, inputs |
| `--surface-sunken` | skeletons, code, plain badges |
| `--border` | dividers between rows and items |
| `--border-control` | input and secondary button borders, table header rule |
| `--text`, `--text-muted` | body text, secondary text and table headers |
| `--accent`, `--accent-hover`, `--on-accent` | links, primary buttons, bars, the active nav item. The only accent colour |
| `--danger`, `--danger-bg` | errors, reject, rejected |
| `--warn`, `--warn-bg` | rising, waiting |
| `--ok`, `--ok-bg` | accepted, edited |
| `--focus` | the focus ring |

Radius: `--radius-control` (6px) on buttons, inputs, badges and notices; `--radius-panel`
(8px) on cards, panels and the table wrapper. Spacing is in multiples of 4px. Body text is
15px.

## Component classes

| Class | When |
|---|---|
| `btn` plus `btn-primary` | the main action in a view (Log in, Draft suggestions, Accept, Save edit) |
| `btn` plus `btn-secondary` | other actions (Edit, Cancel, Show more, Log out) |
| `btn` plus `btn-danger` | actions that throw something away (Reject). Never the only button |
| `btn-small`, `btn-block` | header-sized and full-width variants |
| `table-wrap` around `table.data-table` | every data table. Scrolls inside itself with a sticky header, so the page never scrolls sideways. Give it `tabIndex={0}` so keyboard users can scroll it |
| `num` | every numeric cell and its header: right-aligned, tabular figures |
| `share`, `share-track`, `bar` | a 0 to 1 share as a small bar plus the number. No background track |
| `badge`, `badge-warn`, `badge-ok`, `badge-danger` | a status in words ("Rising", "Accepted"). No coloured dots |
| `card` | only for suggestions, or other self-contained items a person decides on. Lists of comments use dividers, not cards |
| `card-grid` | a grid of cards |
| `panel` | a single boxed form (login) |
| `page-head`, `section-head`, `toolbar` | page title block, section title with an action on the right, filters row |
| `field`, `field-inline` | a label above its input, or beside it in a toolbar |
| `muted`, `small` | secondary text |
| `empty`, `notice`, `notice-error` | rendered by the components in `states.tsx`; don't hand-roll them |

## States every view needs

Every view that loads data has all four, using `src/states.tsx`:

1. Loading: `SkeletonRows` inside the real `<tbody>` with the same column kinds as the header, or `SkeletonBlocks` (`card` when cards will appear). No spinners.
2. Empty: `EmptyState` that says how to fill it, for example "No issues yet. Run `python -m kaizen.issues build`".
3. Error: `ErrorNotice error={e}`. Keep the caught value as `unknown` and pass it in; `describeError` turns status 0, 403, 404, 409, 422 and 5xx into plain words. 401 never reaches a page, it goes to login.
4. Data.

Actions (buttons that POST) show their own `ErrorNotice` next to the button and disable
the button while the request runs.

## Accessibility (NFR4)

- Every input has a `<label htmlFor>`. Placeholder text is not a label.
- Actions are `<button type="button">` or `type="submit"`; navigation is `<Link>`. No clickable divs or spans.
- Tables have a `<caption>`, `<th scope="col">` headers, and the item's name as `<th scope="row">`.
- Focus is visible on everything (`:focus-visible`, 3px `--focus` outline). Never set `outline: none` without a replacement.
- Status words go in text, never colour alone. Bars and decorative elements get `aria-hidden="true"` and the number stays in text.
- Errors use `role="alert"`; progress and counts use `role="status"`.
- Animation and transitions are switched off under `prefers-reduced-motion`.
- Check 375px wide: nothing but the table scrolls sideways.
- Don't disable a submit button to signal missing input; let it submit and say what is missing.

## Writing

Follow "Writing" in the root `AGENTS.md`. For UI strings in particular: no em or en
dashes (use a comma or a full stop), no "Welcome back", no emoji, plain verbs on buttons
("Draft suggestions", "Reject"), and error text that says what to do next.

## Run and verify

The back end, from `backend/` with its virtual environment active:

```
uvicorn kaizen.api.app:create_app --factory --reload
```

Set `KAIZEN_DATABASE_URL` first to use a database other than the default SQLite file.
The issues page is empty until `python -m kaizen.issues build` has run on that database.

Then here:

```
npm ci
npm run dev      # http://localhost:5173
npm run build    # tsc --noEmit, then vite build; CI runs this
```

A test account: `python -m kaizen.cli create-user <name> --role qi` (or `--role manager
--unit ED`). It asks for the password with `getpass`, which reads from the console, so on
Windows piping a password in does not work, and an agent without a console cannot answer
the prompt. Either run it yourself in a terminal, or patch `getpass` in a throwaway
script outside the repo:

```python
import getpass, sys
import kaizen.cli
getpass.getpass = lambda prompt="": "a-test-password-of-10-plus-chars"
sys.argv = ["kaizen.cli", "create-user", "testqi", "--role", "qi"]
kaizen.cli.main()
```

Run it with the same `KAIZEN_DATABASE_URL` as uvicorn. Never commit the password or the
script.

To check an endpoint and its reply shape through the proxy:

```
curl -s -H "Content-Type: application/json" -d '{"username":"testqi","password":"..."}' http://localhost:5173/api/auth/login
curl -s -H "Authorization: Bearer <token>" http://localhost:5173/api/issues
```

Before pushing: `npm run build` with no errors, then `python scripts/check_repo.py` from the
repo root. Look at the page in light and dark and at 375px wide.

## How to add a page

`IssuesPage.tsx` is the model for a table page; `SuggestionsPage.tsx` for a list of cards
with a filter.

1. Add the reply types and a method to the `api` object in `src/api.ts`, copied from the handler. Note the backend file in the table above.
2. Check the shape with curl through the proxy against a real database.
3. Copy the model page to `src/pages/NewPage.tsx`. Keep its structure: `data` and `error` state, one `useEffect` that calls `api`, then the four states in order (error, empty, skeleton, data).
4. Use the classes above. Numbers get `num`, statuses get a `badge`, tables go inside `table-wrap`.
5. Add the route in `App.tsx` inside `RequireLogin`. If only QI can use it, wrap it like `/suggestions` and hide the nav link the same way.
6. Add a `NavLink` in `Header` if it is a top-level page.
7. Run `npm run build`, open it in light, dark and at 375px, and tab through it with the keyboard.
8. Update the layout in this file and tick the item off in `TASKS.md`.
