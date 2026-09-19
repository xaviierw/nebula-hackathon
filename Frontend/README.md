# Nebula Frontend

The single app that houses every subsystem model, as required by the hackathon
brief (§4.1 item 3). This is currently a **navigation skeleton only** — no
uploads, no predictions, no backend calls.

## Running it

```bash
cd Frontend
npm install
npm run dev          # http://localhost:5173
```

Other scripts: `npm run build`, `npm run preview`, `npm run lint` (oxlint).

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
