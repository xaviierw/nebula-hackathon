# Nebula Frontend

The single app that houses every subsystem model, as required by the hackathon
brief (§4.1 item 3). The Rail Corrugation page is connected to the shared
FastAPI backend; the other pages are integrated independently.

## Running it

```bash
cd Frontend
npm install
npm run dev          # http://localhost:5173
```

Other scripts: `npm run build`, `npm run preview`, `npm run lint` (oxlint).

## Rail Corrugation workflow

Select one or more CSV recordings to create a results queue. The page calls
`POST /api/rail-corrugation/predict-batch`, keeps per-file failures retryable,
and shows the finding, measured evidence, plain-language definitions, review
checklist and review record for each successful item.

Saved batches and reviews persist in browser localStorage under
`nebula.rail.workspace.v1`; raw recordings are never stored there. Users can
download an individual printable HTML review report or the required two-column
`rail_predictions.csv`. Run `npm run test:rail` to check workspace restoration,
filename uniqueness, export formatting and report escaping.

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
