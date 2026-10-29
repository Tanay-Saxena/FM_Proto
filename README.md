# FoodMania — QR menus, honest AI discovery, table ordering and billing

Scan → discover → order → add more → pay. Multi-tenant restaurant platform: guest QR menu, live availability
from admin-managed schedules, grounded recommendations and ask-a-dish chat, kitchen display with distinct
add-on tickets, server-calculated bills, simulated UPI checkout, digital receipts, and an owner dashboard.

> **Status: working local prototype.** Payments, SMS and email are **simulated** (mock providers, clearly labelled).
> No live payment/SMS/email/POS integration exists. See [docs/IMPLEMENTATION_CHECKLIST.md](docs/IMPLEMENTATION_CHECKLIST.md)
> for exactly what is implemented, mocked, partial or planned.

## Quick start (macOS/Linux, no Docker needed)

Prerequisites: Python 3.11+, Node 20+, optional `tesseract` (for image OCR: `brew install tesseract`).

```bash
./scripts/dev.sh          # creates venv, installs deps, seeds demo data, starts API :8010 + web :3000
```
Open http://localhost:3000. Or step by step:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed            # demo data (use --reset to rebuild)
.venv/bin/uvicorn app.main:app --port 8010 --reload
cd ../frontend && npm install && npm run dev      # http://localhost:3000 (proxies /api/v1 → :8010)
```

API docs (OpenAPI): http://localhost:8010/docs

### Also in the prototype
Dish photo upload (Menu → open a dish) · reorder categories/dishes · reviews (rate on the receipt page → Admin → Reviews) ·
refund a payment (owner, Admin → Payments) · move a party to another table / re-open a closed one (Admin → Orders) ·
bill split calculator (guest → My table). Refunds, payments, SMS and email are simulated.

### Demo accounts (password `demo1234`, sample data only)
| Role | Email |
|---|---|
| Owner (Spice Route) | owner@spiceroute.demo |
| Manager / Kitchen / Floor staff | manager@ / kitchen@ / staff@spiceroute.demo |
| Owners of the other venues | owner@kettle.demo, owner@coppertap.demo |
| Platform admin | platform@foodmania.demo |

The landing page lists sample tables; each button opens the same URL a printed table QR would. The guest page has a
**Demo clock** (only when `DEMO_MODE=true`) to jump to lunch, happy hour or closing time and watch availability change.

## Try the core scenario
1. Landing → *Spice Route Kitchen → Table 10*. Demo clock → "12:30 PM · lunch".
2. Add Paneer Tikka + Butter Naan → send to kitchen (enter name + mobile).
3. Sign in as `kitchen@spiceroute.demo` at `/kitchen` → Accept → Start cooking.
4. As the guest, add Gulab Jamun → *Send add-on to kitchen*. The kitchen gets a separate red **ADD-ON B** ticket.
5. Request bill → Pay → simulate failure, retry, simulate success → open the receipt.

## Tests
```bash
cd backend && .venv/bin/python -m pytest -q          # 45 tests: availability, billing, scenarios A–I, ingestion
cd frontend && npx playwright test                    # needs API+web running and Google Chrome installed
```

## Configuration
Backend env vars (see `backend/.env.example`): `DATABASE_URL` (SQLite default; PostgreSQL supported), `SECRET_KEY`,
`PUBLIC_BASE_URL`, `DEMO_MODE`, `PAYMENT_WEBHOOK_SECRET`, `COOKIE_SECURE`, optional `ANTHROPIC_API_KEY`/`LLM_MODEL`.
Frontend: `BACKEND_URL`. **Never run with `DEMO_MODE=true` in a real deployment** (it enables the demo clock and simulated checkout).

## Migrations
`cd backend && .venv/bin/alembic upgrade head` (the dev server also calls `create_all` for convenience). Create new
migrations with `alembic revision --autogenerate -m "..."`.

## Docs
[PROJECT_CONTEXT](docs/PROJECT_CONTEXT.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [API_SPEC](docs/API_SPEC.md) ·
[DECISIONS](docs/DECISIONS.md) · [IMPLEMENTATION_CHECKLIST](docs/IMPLEMENTATION_CHECKLIST.md) ·
[PROJECT_MEMORY](docs/PROJECT_MEMORY.md) · [CHANGELOG](docs/CHANGELOG.md) · [RUNBOOK](docs/RUNBOOK.md) ·
[MASTER_BUILD_SPEC](docs/MASTER_BUILD_SPEC.md)

## Troubleshooting
- *Landing says the demo server isn't reachable* → API not running on :8010 (`BACKEND_URL`).
- *Port 8000/8010 busy* → pick another port and set `BACKEND_URL`.
- *Image import fails with "OCR engine isn't installed"* → install Tesseract.
- *Kitchen shows old tickets* → `python -m app.seed --reset`.
