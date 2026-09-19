# Nebula Frontend

The single app that houses every subsystem model, as required by the hackathon
brief (§4.1 item 3). The Rail Corrugation page is connected to its FastAPI
prediction endpoint; other subsystem pages are being integrated independently.

## Running it

```bash
cd Frontend
npm install
npm run dev          # http://localhost:5173
```

For live Rail Corrugation predictions, also start its FastAPI service by
following `Backend/Rail_Corrugation/README.md`. The Vite development server
proxies `/api` to that service on port 8000.

Other scripts: `npm run build`, `npm run preview`, `npm run lint` (oxlint).

## Rail Corrugation workflow

Select one or more CSV recordings to create a results queue. Each recording is
analysed separately and exposes the finding, measured evidence, explanatory terms,
review checklist and editable review record. Use the queue filters to find flagged,
failed or unreviewed recordings. Failed files can be retried or reselected after a
reload. Duplicate filenames within a batch are rejected; use New batch to analyse
another recording with the same name.

Saved batches and reviews persist in localStorage under `nebula.rail.workspace.v1`
on the same browser/device/origin. Raw recordings are not saved. This is local
persistence for the demo, not a shared team database; download reports before
clearing browser data. Storage failures and conflicting changes from another tab
are shown in the page.

Download an individual HTML review report (standalone, printable to PDF) or the
batch's `rail_predictions.csv`. Combined export includes every successful,
non-excluded recording in upload order, regardless of the queue filter. It is
disabled while files remain unresolved; exclusions produce an explicitly labelled
partial export. Review fields never enter the submission CSV.

Run `npm run test:rail` with Node 24 to check saved-record restoration, interrupted
queues, filename uniqueness, CSV formatting and report escaping.

## Where things live

| Path | What it is |
|---|---|
| `src/App.tsx` | The whole route tree |
| `src/subsystems.ts` | The four subsystems, declared once |
| `src/pages/subsystems/` | One page per subsystem — **build your subsystem here** |
| `src/components/` | Shared UI (`AppShell`, `SubsystemCard`) |
| `src/auth/` | Placeholder auth + the route guard |
| `src/api/client.ts` | `apiFetch()` — the single place to call the backend |

## Adding your subsystem

Replace the `<SubsystemPlaceholder />` call in your page under
`src/pages/subsystems/` with real UI. Everything else — routing, the dashboard
card, the header — already works. Edit `src/subsystems.ts` to change a display
name or blurb.

## Things to know

- **Login accepts anything**, including an empty form. `src/auth/AuthProvider.tsx`
  is the one file to change when real auth arrives.
- **Tailwind v4** — there is no `tailwind.config.js` and v4 does not use one.
  Do not run `npx tailwindcss init`; that is v3 muscle memory.
- **Call the API with `apiFetch('/door/predict', ...)`**, not an absolute URL.
  Paths stay relative so requests are same-origin in dev (Vite proxies `/api`
  to `127.0.0.1:8000`) and in production. CORS then never applies.
- **`@/` is aliased to `src/`**, so `import { useAuth } from '@/auth/useAuth'`
  works instead of counting `../`s.
