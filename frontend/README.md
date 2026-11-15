# Kaizen front end

React 19 and TypeScript, built with Vite. Owner: Aansh (P3 Table 8: FR5, FR6, FR8, NFR4).
No UI library and no state library; the only runtime dependencies are React and React
Router. Versions are pinned exactly in `package.json`, so `npm ci` gives everyone the same
build.

## Running it

You need Node 24 and npm 11. Start the API first, from `backend/` with its virtual
environment active (see the main README for the install and for creating an account):

```
uvicorn kaizen.api.app:create_app --factory --reload
```

Then in a second terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and log in with an account made by `python -m kaizen.cli
create-user`. The issues page is empty until `python -m kaizen.issues build` has run on the
server's database.

The app calls the API as `/api/...`. In development Vite forwards those requests to
http://localhost:8000 and removes the `/api` prefix, so the back end needs no CORS
settings. A production deploy needs the same rule in whatever serves `dist/`; that isn't
set up yet.

`npm run build` runs `tsc --noEmit` and then `vite build` into `dist/`. CI runs the same
command in the "Front end build" job, so a type error fails the PR.

## How it is built

Four pages: login, the ranked issues table, an issue's comments with their labels (and,
for QI staff, its suggestions beside them), and the suggestion review queue. Every view
has a loading skeleton, an empty state that says how to fill it, and an inline error that
says what the status code means. Light and dark follow the system setting.

Managers only get their own unit's issues and comments from the API, and the app hides the
Suggestions link, the draft button and the review queue from them, since those endpoints
return 403 for managers.

Logging out only forgets the token in the browser. The API has no logout endpoint, so the
token stays valid on the server until it expires after 12 hours.

The folder layout, how the API client and its types work, the design tokens and classes,
the accessibility rules and a recipe for adding a page are in [AGENTS.md](AGENTS.md).
It is written for coding agents, but it is the reference for people too.

Screenshots of each page in light, dark and at 375px wide are in `docs/screenshots/`.

## Accessibility (NFR4)

Labels on every input, real buttons, tables with captions and header cells, a visible
focus ring, a skip link, and colour pairs checked for WCAG 2.1 AA in both light and dark
(the numbers are at the top of `src/styles.css`). The top issue's comments are one click
from the issues page. Nobody has run an automated scan, a screen reader pass or the SUS
test yet; those are in [TASKS.md](TASKS.md).

## Not tested yet

The suggestion card has only been checked against the API's error replies (404 for an
unknown suggestion, 422 for an empty edit), not against a real drafted suggestion, because
drafting calls the LLM and the local test database has none.

## Next steps

The comparison view (FR5), label correction, redaction, rename and merge (FR6), comment
filters and CSV export (FR8), and the accessibility scan and SUS test (NFR4) are still to
do. [TASKS.md](TASKS.md) has each one with its endpoint, reply shape, which page to copy
and how to check it.
