# Runbook

**Backup (SQLite dev):** copy `backend/foodmania.db` (stop the API or use `sqlite3 .backup`). **Postgres:** `pg_dump -Fc`; restore with `pg_restore`. Uploaded menus live in `backend/storage/` (local disk — use object storage in production).
**Migrate:** `cd backend && alembic upgrade head`. Create: `alembic revision --autogenerate -m "msg"`; review the diff before applying.
**Reset demo:** `python -m app.seed --reset` (destroys all data in the configured DB).
**Contact retention:** guest name/phone/email live on `table_sessions`; receipts never expose them. There is no automated purge yet — plan: null the contact columns on sessions closed > N days (set `contact_purged_at`). Record consent text and retention period per jurisdiction before a pilot.
**Production checklist:** `DEMO_MODE=false`, strong `SECRET_KEY` and `PAYMENT_WEBHOOK_SECRET`, `COOKIE_SECURE=true`, Postgres, object storage, a real queue/worker (the in-process notification worker is single-instance), shared rate limiter (Redis), real payment/SMS/email adapters with sandbox testing, HTTPS, log shipping.
**Choosing Railway vs GCP:** needs Postgres + object storage + a worker process + secrets. Railway is faster to stand up; Cloud Run + Cloud SQL + GCS gives more control. Decide after provider selection.
