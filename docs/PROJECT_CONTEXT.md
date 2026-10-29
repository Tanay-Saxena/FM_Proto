# Project context

**What it is:** multi-tenant restaurant platform. Guests scan a table QR, browse a live menu, get honest recommendations,
order (and add more while earlier tickets cook), then pay. Kitchen staff use a ticket board; owners manage menus,
schedules, promotions, tables, imports, payments and settings — all without code changes.

**Runtime:** FastAPI (:8010) + SQLite file (`backend/foodmania.db`) · Next.js (:3000) proxying `/api/v1`.
**Real vs simulated:** *Real* — auth/RBAC, tenancy, availability engine, billing, order/session state machines, OCR/PDF ingestion,
webhook signature verification, idempotency, receipts (PDF). *Simulated* — payment provider, SMS, email, POS. *Optional/untested* — Anthropic LLM adapter.
**Folder guide:** see ARCHITECTURE.md. **Business rules to know:** DECISIONS.md D-007…D-012.
**Demo data:** 3 sample venues (`is_demo=true`), password `demo1234`; `python -m app.seed --reset` rebuilds.
