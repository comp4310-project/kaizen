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

## Layout

```
index.html                 page shell, loads src/main.tsx
vite.config.ts             dev server on 5173 and the /api proxy
src/main.tsx               mounts the app inside the router and login state
src/App.tsx                header, routes, and the login guard
src/api.ts                 every API call and the TypeScript types for its replies
src/auth.tsx               who is logged in, from /me; the token is in sessionStorage
src/format.ts              small text helpers (label values, percentages, UTC times)
src/SuggestionCard.tsx     one suggestion with citations, accept, edit and reject
src/pages/LoginPage.tsx
src/pages/IssuesPage.tsx       ranked issues table (FR4, FR8)
src/pages/IssueDetailPage.tsx  comments behind an issue with their labels, and drafting (FR7)
src/pages/SuggestionsPage.tsx  review queue, filtered by status (FR7, NFR2)
src/styles.css             all styles
```

The types in `src/api.ts` are copied by hand from the handlers in
`backend/kaizen/api/`. When a reply changes on the back end, change the type in the same
PR.

Roles come from `/me`. Managers see the issues table and issue comments for their own unit
only, which the API already enforces. They get no Suggestions link, no "Draft suggestions"
button, and `/suggestions` sends them back to the issues page, since those endpoints return
403 for them.

Logging out only forgets the token in the browser. The API has no logout endpoint, so the
token stays valid on the server until it expires after 12 hours.

## Accessibility (NFR4)

Every input has a `<label>`, every action is a `<button>`, and the issues table uses
`<caption>`, `<th scope>` and a row header for the issue name. Keyboard focus shows a 3px
orange outline. Text colours are at least 4.5:1 against their background; the values are
noted at the top of `styles.css`. A skip link jumps past the header. The top issue's
comments are one click from the issues page. Nobody has run an automated scan or a screen
reader over it yet.

## Not tested yet

The suggestion card has only been checked against the API's error replies (404 for an
unknown suggestion, 422 for an empty edit), not against a real drafted suggestion, because
drafting calls the LLM and the local test database has none.

## Next steps

These pages still need building. The endpoints are being added on a separate back end
branch, so check the final request and reply shapes in `/docs` before writing the types.

| Page or control | Endpoint | Requirement |
|---|---|---|
| Patient and staff comparison by category, stage or unit, marking where only one group reports a problem | `GET /compare?by=category\|stage\|unit` | FR5 |
| Confirm or correct a comment's labels (urgency, stage, categories), on the issue detail page | `POST /comments/{id}/labels` | FR6 |
| Redact a personal detail that de-identification missed | `POST /comments/{id}/redact` | FR6 |
| Rename an issue | `POST /issues/{id}/rename` | FR6 |
| Merge two issues | `POST /issues/{id}/merge` | FR6 |
| Download an issue's comments as CSV, matching the filtered view | CSV export of issue comments | FR8 |

FR8 also asks for filters on the dashboard (by unit, source and stage), which the issues
table doesn't have yet. The FR6 controls are QI only, so hide them for managers the same
way the draft button is hidden.
