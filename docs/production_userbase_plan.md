Forge production userbase and secure data roadmap
Generated: 2026-06-16

Current state
- Forge is still primarily a local single-user health dashboard.
- A production account foundation now exists:
  - user_accounts
  - auth_sessions
  - data_connections
  - audit_logs
  - /api/auth/signup
  - /api/auth/login
  - /api/auth/me
  - /api/auth/logout
- The Profile tab has a browser account panel for creating/logging into a Forge account.
- Existing dashboard, goals, metrics, Garmin sync, and coach routes are not yet fully user-scoped.

What must be completed before public signup

1. User-scope every data table
- Add user_id to health_snapshots.
- Add user_id to goals and goal_streak.
- Add user_id to coach_summaries.
- Add user_id to future sync_jobs/activity tables.
- Add user_id indexes.
- Replace unique health_snapshots.date with a compound uniqueness rule: user_id + date.
- Replace singleton user_profiles.id=1 with user-scoped profiles.

2. Protect every private route
- Require bearer auth for profile, dashboard, goals, sync, coach, metrics, insights, special metrics, and body composition routes.
- Every query must filter by current_user.id.
- Add tests that user A can never read or modify user B data.
- Keep an explicit local-dev bypass only if FORGE_ENV=development.

3. Migrate local data safely
- Create a first local owner account.
- Attach existing health_snapshots, goals, profile, and coach rows to that account.
- Keep a backup before migration.
- Add an idempotent migration script.

4. Secure health-data connections
- DataConnection stores provider state per user.
- Garmin private beta:
  - Do not store plaintext Garmin passwords.
  - Prefer saved garth tokens encrypted at rest.
  - Add token-expired status.
  - Add disconnect and delete-token flow.
- Garmin public product:
  - Apply for Garmin Health API partner access.
  - Use official OAuth/token flow if approved.
- Apple Health:
  - Requires iOS/HealthKit companion app.
  - Web-only Netlify app cannot directly read Apple Health.

5. Sync architecture
- Add sync_jobs table with user_id, provider, status, progress_pct, current_date, fetched, failed, started_at, finished_at, error.
- Initial sync: 365 days.
- Subsequent sync: delta from user's last synced date.
- Background sync worker per user.
- Frontend shows data freshness and sync progress.
- Retry failed days without refetching everything.

6. Privacy and compliance
- Add consent screen for health-data processing.
- Add export-my-data endpoint.
- Add delete-account-and-data endpoint.
- Add audit logs for login, sync, export, delete, and connection changes.
- Add privacy policy and terms.
- Avoid sending raw health data to frontend logs, analytics, or error trackers.
- Encrypt provider tokens at rest.

7. Deployment path
- Frontend: Netlify.
- Backend: Render, Railway, Fly.io, AWS, Azure, or GCP.
- Database: managed Postgres.
- Required env:
  - DATABASE_URL
  - CORS_ORIGINS=https://your-netlify-site.netlify.app,https://app.yourdomain.com
  - OPENAI_API_KEY
  - OPENAI_MODEL
  - GARMIN/connection secrets only on backend
- Never expose Garmin/OpenAI secrets through VITE_* variables.

8. Production QA
- Signup/login/logout happy path.
- Password validation and duplicate email handling.
- Route protection.
- Cross-user isolation tests.
- Data export/delete tests.
- Garmin token expiry tests.
- Sync interruption and retry tests.
- Browser QA on Chrome, Safari, mobile Safari.
- Accessibility pass.

Recommended implementation order
1. Add user_id columns and migrations.
2. Create local owner migration.
3. Protect profile/dashboard/goals first.
4. Protect metrics/insights/coach.
5. Move Garmin sync to per-user DataConnection.
6. Add sync_jobs and progress UI.
7. Add export/delete account.
8. Deploy frontend to Netlify and backend to managed host.
9. Run cross-user isolation and privacy QA.
