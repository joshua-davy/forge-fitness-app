# Forge Security Release Checklist

## Credential incident response

- [ ] Rotate or revoke any Garmin session whose token files were ever committed.
- [ ] Confirm `backend/garmin_session/` remains ignored and is never deployed.
- [ ] Do not place API keys, database URLs with passwords, or provider tokens in source files, screenshots, tickets, or client-side environment variables.

## Encryption at rest

The local SQLite database is **not encrypted at rest**. Forge encrypts provider token blobs with Fernet, and passwords are stored as PBKDF2 hashes, but health data, profiles, sessions, and audit records require disk/database encryption before a production release. Use managed PostgreSQL with encrypted volumes, TLS, backups encrypted with a managed key, and a managed secret store for `FORGE_CONNECTION_ENCRYPTION_KEY`.

This checklist separates what is safe for local account testing from the work
that must be approved before inviting public users.

## Implemented for local testing

- Forge passwords are salted PBKDF2 hashes, not plaintext.
- Browser sessions are random bearer tokens; only token hashes are persisted.
- New passwords use a 600,000-round PBKDF2-HMAC-SHA256 work factor; sensitive
  sign-in and Garmin credential routes have a local rate limiter.
- Garmin passwords and MFA codes are used only for the connection request.
- Garmin token bundles are encrypted at rest with Fernet and stored per Forge
  account in `data_connections`.
- Health snapshots, coach history, goals, and profiles are account-scoped.
- Legacy pre-account health rows are assigned to reserved owner `user_id = 0`
  during migration, so they are not exposed to newly created accounts.
- The API sends `nosniff`, anti-framing, referrer, and permissions headers.

## Required before public signup

1. Set a high-entropy `FORGE_CONNECTION_ENCRYPTION_KEY` in the deployment
   secret store. Do not rely on the development key file.
2. Move browser auth from `localStorage` bearer tokens to short-lived,
   `HttpOnly`, `Secure`, `SameSite` cookies. Add CSRF protection at the same
   time.
3. Replace the local in-process rate limiter with Redis-backed rate limiting,
   account lockout, and abuse monitoring for every public instance.
4. Add email verification, password reset, verified email delivery, and
   account/session management.
5. Move production storage to Postgres and replace startup schema changes with
   versioned Alembic migrations.
6. Use Redis or another shared TTL store for Garmin MFA challenges and sync
   jobs. The current in-memory challenge is intentionally single-process.
7. Add background sync workers, retries, monitoring, token-refresh alerts,
   and an audit trail that never includes credentials or health payloads.
8. Complete a Garmin Terms-of-Service and data-use review. The current
   `python-garminconnect` route is unofficial and should not be assumed
   suitable for a public commercial product.
9. Implement privacy policy, consent capture, data export, account deletion,
   retention limits, encryption/backups, and incident response procedures.
10. Add a CSP, HSTS, HTTPS-only deployment, dependency scanning, secret
    scanning, and security logging with redaction.

## Apple Health note

Apple Health data cannot be pulled directly from a normal browser. It needs an
iOS companion app using HealthKit, then an authenticated upload API. Health
Connect plays the analogous role on Android.
