# Forge

Forge is a local-first health intelligence dashboard. It stores one account's
Garmin-derived metrics, deterministic scores, profile data, goals, and coach
history separately from every other account.

## Current capability

- Email/password account creation and sign-in.
- Per-account encrypted Garmin sessions, including an MFA completion step.
- User-scoped Garmin history import, daily sync, calculated recovery,
  readiness, strain, sleep, fitness age, biological age, body composition,
  trends, focus areas, and coach recommendations.
- Profile editing and saved body-composition metrics.
- Web dashboard with historical date navigation and metric drill-down charts.

No synthetic health metric source remains in the live backend. A missing
Garmin field is represented as missing data rather than a plausible-looking
number.

## Run locally

Double-click `start-forge.cmd`. It checks dependencies, starts FastAPI at
`http://127.0.0.1:8001`, starts the web app at `http://127.0.0.1:5173`, and
opens the dashboard.

To verify the project manually:

```powershell
cd backend
python -m pytest -q

cd ..\web
npm run build
```

## Account and Garmin flow

1. Create a Forge account or sign in.
2. On the account page, connect Garmin using that user's credentials.
3. Complete Garmin's MFA prompt when present.
4. Import history. Garmin session tokens are encrypted in the database; Forge
   does not persist Garmin passwords or MFA codes.

Garmin's unofficial `python-garminconnect` route is intended for local
testing. A public commercial release must use an approved Garmin integration
or a user-controlled import method after a terms-of-service review.

## Deployment safety

Read [the security release checklist](docs/security-release-checklist.md)
before inviting public users. In particular, production needs Postgres with
versioned migrations, HTTPS, a high-entropy
`FORGE_CONNECTION_ENCRYPTION_KEY`, managed sessions, rate limiting, email
verification, account recovery, privacy controls, and background workers.

## Configuration

Copy `backend/.env.example` to `backend/.env` for local configuration.

- `DATABASE_URL`: SQLite is fine for local testing. Use Postgres in production.
- `OPENAI_API_KEY`: optional; deterministic coaching remains available without
  it.
- `CORS_ORIGINS`: comma-separated permitted frontend origins.
- `FORGE_CONNECTION_ENCRYPTION_KEY`: required in production to encrypt Garmin
  session tokens.
