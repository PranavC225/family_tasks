# family-tasks

Private shared to-do app for a family of 4. FastAPI + HTMX (server-rendered), SQLModel over a
DB-agnostic `DATABASE_URL` (SQLite local, Neon Postgres prod), Google OAuth restricted to a
4-email allowlist. Containerized for Google Cloud Run (free tier). Mobile-first.

## Lifecycle
Active → (complete) → Done → (reactivate) → Active. Any task → (archive) → Archived → (unarchive) → Active.
"Done" = removed from the active list but retained. "Archived" = permanent storage.

## Rules
- uv only (never pip/poetry directly). Run: `uv run uvicorn family_tasks.main:app --reload`.
- Keep DB access DB-agnostic — never write SQLite- or Postgres-specific SQL.
- Auth is the email allowlist in `ALLOWED_EMAILS`; the access gate lives in `auth.py:auth_callback`.
- ruff + mypy (strict) + pytest must stay green. Conventional Commits.
- Never commit `.env` or `*.db`. Never push to remote without explicit instruction.

## Run locally without Google
Set `ENV=development` and visit `/auth/dev-login`.

## Notifications (Web Push)
Task creation fires a Web Push (VAPID) notification — no Firebase/FCM project, no Telegram. Cost is
**$0**: the browser push services (Chrome → FCM's web-push endpoint, Firefox → Mozilla, Safari →
APNs) are free; only your own Cloud Run compute sends the request.

- **Recipients**: if the task has `assigned_to_email`, only that person is notified (skipped if
  they're the creator). If it's a general task (no assignee), everyone in `ALLOWED_EMAILS` except
  the creator is notified. See `tasks.py:recipients_for`.
- **Keys**: generate once with `uv run python scripts/gen_vapid.py`, paste the three `KEY=value`
  lines into `.env`. `VAPID_PRIVATE_KEY` is base64-encoded PEM and is a secret; `VAPID_PUBLIC_KEY`
  is the public `applicationServerKey` the browser uses to subscribe — safe as a plain env var.
- **Storage**: `PushSubscription` table (one row per browser/device) is created automatically by
  `create_all()` on next startup — no migration needed.
- **Pruning**: dead subscriptions (push service returns 404/410) are deleted automatically the next
  time a notification targets them — see `push.py:_send`.
- **Frontend**: `static/sw.js` (service worker), `static/push.js` (subscribe flow), the 🔔 button in
  `base.html`. All-Android target today — works straight from the browser tab, no install step.

### Enabling iOS later
iOS Safari only delivers Web Push to a PWA added to the **Home Screen** (Settings → Share → Add to
Home Screen), and only 16.4+ — it never works from a normal Safari tab. No server code changes are
needed; when an iPhone joins the family:
1. Replace the placeholder `static/icon-192.png` / `icon-512.png` with real icons (the manifest
   already references them).
2. Add an `apple-touch-icon` `<link>` in `base.html` pointing at a real icon.
3. Each iPhone user: open the site in Safari → Add to Home Screen → open the app from the Home
   Screen icon (not Safari) → tap 🔔 Notify.

## Deploy (live setup — done)
Runbook is PLAN.md §14; this is the actual state after following it.

- **Source**: GitHub `PranavC225/family_tasks`, branch `main`. Cloud Build trigger watches `^main$` —
  every push to `main` rebuilds the Dockerfile and deploys a new Cloud Run revision automatically.
  No manual deploy step.
- **GCP project**: `family-tasks` (dedicated, "No organisation"). APIs enabled: Cloud Run Admin,
  Cloud Build.
- **Cloud Run service**: `family-tasks`, region `europe-west4` (Netherlands). Allow public access
  (auth is handled in-app, not by Cloud Run IAM), request-based billing, ingress: all,
  min-instances=0 (free-tier scale-to-zero, accepts cold start).
- **Database**: Neon Postgres, region `eu-central-1` (Frankfurt). Neon Auth is off — unused, the app
  has its own OAuth.
- **Secrets**: `SECRET_KEY`, `DATABASE_URL`, `GOOGLE_CLIENT_SECRET` are in Secret Manager, referenced
  as env vars on the Cloud Run service (not plaintext). The Cloud Run service's default compute
  service account has the `Secret Manager Secret Accessor` role. `ENV`, `BASE_URL`,
  `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS` are plain env vars (non-secret).
- **OAuth consent screen**: External, Testing mode (not published — under 100 test users, no Google
  verification needed). Test users = the 4 family emails, matching `ALLOWED_EMAILS`.
- **Schema changes**: `init_db()` only runs `create_all()` on startup — it creates missing tables but
  does NOT alter existing ones. Changing a model's columns after the first deploy needs a manual
  migration (e.g. `ALTER TABLE` against Neon, or introduce Alembic) — `create_all()` won't do it.

## Releasing a change
Commit locally, `git push origin main` — the Cloud Build trigger picks it up and redeploys
automatically. Watch progress under Cloud Build → History or the Cloud Run service's Revisions tab.
