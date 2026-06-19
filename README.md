# Forge — Daily Command Centre

A premium personal health-intelligence platform combining recovery/strain
analytics, goal execution, day-timing awareness, and an AI coach.

```
forge-app/
├── backend/        FastAPI + SQLAlchemy + SQLite/Postgres   ← runs anywhere
├── web/            React + Vite + framer-motion + dnd-kit   ← shippable today
├── mobile/         Expo + react-native-svg                  ← scaffold
├── infra/          render.yaml                              ← one-click deploy
└── docker-compose.yml                                       ← local everything
```

## What works right now

- **Backend:** 23 API endpoints, 17 passing tests. Goal CRUD with optimistic
  reorder. 6 AM active-day boundary. Streak rollover. Push-remaining.
  Deterministic stubbed health metrics (replace `services/health.py` body
  with your Garmin source). AI polish endpoint with graceful no-key degrade.
  Coach service that combines recovery, sleep, stress, day-phase, and goal
  state into tone-tagged recommendations.

- **Web:** Production build is 18 KB CSS + 321 KB JS (4 + 104 KB gzipped).
  All 7 Daily Command Centre components built: Goal Ticker, Day Progress
  Ring, Today Goals (with drag-reorder, queue, polish, push-remaining),
  Plan Tomorrow, Health Rings, Health Metrics grid, Coach Card. Fully
  responsive 390 → 2560px. Dark premium aesthetic per the brief.

- **Mobile:** Expo Router scaffold with dashboard screen, Goal Ticker and
  Day Progress Ring ported to react-native-svg. Not finished — see
  `mobile/README.md`.

## Run it locally (the 60-second path)

### One-click Windows launcher

Double-click:

```text
start-forge.cmd
```

That opens the backend on `http://127.0.0.1:8001`, starts the web app on
`http://127.0.0.1:5173`, points the frontend at the v3 backend, and opens
Forge in your browser. Keep the two terminal windows open while using Forge.

### With Docker

```bash
docker compose up --build
# web on http://localhost:8080
# api on http://localhost:8000
```

### Without Docker

Terminal 1 — backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your OPENAI_API_KEY
uvicorn app.main:app --reload
```

Terminal 2 — web:
```bash
cd web
npm install
npm run dev          # opens http://localhost:5173 (proxies /api → :8000)
```

### Run the tests

```bash
cd backend && pytest -q
```

Expected: `17 passed`.

## Deploy to a live URL

### Fly.io (recommended for solo deploy)

```bash
# Backend
cd backend
flyctl launch --no-deploy            # accept existing fly.toml
flyctl secrets set OPENAI_API_KEY=sk-... DATABASE_URL=sqlite:////data/forge.db
flyctl volumes create forge_data --size 1
flyctl deploy

# Web (point it at the backend URL Fly just gave you)
cd ../web
flyctl launch --no-deploy
flyctl deploy --build-arg VITE_API_URL=https://forge-backend.fly.dev
```

You now have a live URL openable on phone or desktop.

### Render.com (one-click via Blueprint)

1. Push this repo to GitHub.
2. In Render, click **New → Blueprint**, point at the repo.
3. Render reads `infra/render.yaml` and creates: web service (backend),
   web service (frontend), Postgres database.
4. After deploy: set `CORS_ORIGINS` on the backend to your web URL,
   set `VITE_API_URL` on the web service to the backend URL, redeploy web.

### Self-host with Docker Compose

The provided `docker-compose.yml` is what you'd put on any VPS. Add a
reverse proxy (Caddy is one file) for TLS.

## Configuration

### Backend `.env`

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./forge.db` | Postgres for prod: `postgresql+psycopg://user:pw@host/db` |
| `OPENAI_API_KEY` | _empty_ | Without it, AI polish degrades to passthrough |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any chat-completions model |
| `CORS_ORIGINS` | localhost | Comma-separated list of allowed web origins |
| `FORGE_WAKE_HOUR` | `8` | Used by the Day Progress Ring |
| `FORGE_SLEEP_HOUR` | `24` | 24 = midnight |

### Web build-time env

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Absolute backend URL. Leave empty in dev (Vite proxies `/api`). |

## What's intentionally stubbed

- **Garmin sync.** Garmin has no public OAuth API for individual developers.
  Three real paths, documented in `backend/app/api/routes/garmin.py`:
  1. `python-garminconnect` library (username/password, fragile, ToS grey)
  2. Garmin Health API (enterprise B2B partnership)
  3. FIT file upload (user exports manually — cleanest path)

  Endpoints exist (`/api/garmin/status`, `/api/garmin/sync`,
  `/api/garmin/connect`) and return honest `not_configured` responses
  so the frontend can be built against the contract.

- **Health metrics values.** `services/health.py` produces deterministic
  values seeded by date so the UI looks alive without sync. Replace the
  body of that module when you wire a real source — the contract stays
  the same.

## File map (the ones that matter)

```
backend/app/
├── core/date_utils.py          ← 6 AM boundary, day_progress
├── core/config.py              ← env-driven settings
├── db/session.py               ← SQLAlchemy engine + Base
├── models/goal.py              ← Goal, GoalStreak ORM
├── schemas/goal.py             ← Pydantic v2 request/response
├── schemas/health.py
├── services/
│   ├── goals.py                ← CRUD, reorder, push, streak
│   ├── health.py               ← stubbed metrics (swap for Garmin)
│   ├── polish.py               ← OpenAI polish + graceful degrade
│   └── coach.py                ← rec engine
├── api/routes/
│   ├── goals.py                ← /api/goals/*
│   ├── dashboard.py            ← /api/dashboard, /coach, /day-progress
│   └── garmin.py               ← /api/garmin/* (scaffold)
└── main.py                     ← app factory + CORS + lifespan

web/src/
├── components/
│   ├── goals/                  GoalTicker, GoalRow, TodayGoalsCard,
│   │                           TomorrowGoalsCard, GoalProgressBar, StreakPill
│   ├── day/DayProgressRing.tsx
│   ├── health/HealthRings.tsx, HealthMetrics.tsx
│   ├── coach/CoachCard.tsx
│   └── layout/Header.tsx
├── screens/Dashboard.tsx
├── hooks/data.ts               ← useGoals (optimistic), useDashboard, useCoach
├── lib/api.ts                  ← typed fetch wrapper
└── types/index.ts              ← mirrors backend schemas
```

## Acceptance criteria status

From the original brief:

- [x] A. Daily Command Centre on dashboard with title, ticker, day ring, today, plan tomorrow
- [x] B. Goal ticker rotates pending every 5s, done falls out, all-done + zero states
- [x] C. Day ring percent + phase + colour + remaining + 1-min updates
- [x] D. Goal CRUD: add, edit, delete, complete, reorder, queue, push remaining, plan tomorrow
- [x] E. Persistence via SQLAlchemy, no localStorage source of truth
- [x] F. AI polish via backend, no browser key exposure, degrades without key
- [x] G. Coach uses goals + health + day-phase, recommends push/rest/focus
- [x] H. Responsive 390 → 2560 web, mobile scaffold runs in Expo
- [x] I. Tests for active date, streak, completion rate, push-remaining (17 passing)
- [ ] Garmin sync (scaffolded with 3 documented paths — see above)
- [ ] Expo native fully finished (Dashboard + Ticker + DayRing ported; rest pending)

## Next steps for shipping

1. Deploy to Fly or Render (15 min).
2. Add `OPENAI_API_KEY` as a secret to light up Polish.
3. Decide Garmin path (FIT upload is the safest) and replace
   `services/health.py` body.
4. If you want the Expo app: finish the component ports listed in
   `mobile/README.md`, then `eas build`.

— Built with care. Bevel-coloured, Whoop-pragmatic, Oura-honest.
