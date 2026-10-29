# Architecture

```
FoodMania/
├── backend/                FastAPI + SQLAlchemy 2 + Alembic
│   ├── app/
│   │   ├── main.py         app, error envelope, request-id logging, in-process notification worker
│   │   ├── config.py db.py security.py deps.py ratelimit.py defaults.py schemas.py models.py
│   │   ├── routers/        public.py (guest) · auth.py · admin.py (dashboard + kitchen) · webhooks.py
│   │   ├── services/       domain logic — availability, billing, recommend, chat, orders, sessions,
│   │   │                   receipts, ingestion, menu(_admin), audit, errors
│   │   ├── providers/      adapters: payments (mock), messaging (mock sms/email), llm, storage (local)
│   │   └── seed.py         3 sample venues + Table 12 add-on scenario + paid/failed-notification examples
│   ├── alembic/            migrations     └── tests/   pytest (unit + API scenarios)
├── frontend/               Next.js (App Router, TS), Tailwind 4, Radix Dialog, TanStack Query, Recharts
│   ├── src/app/            / · /r/[slug] (guest) · /t/[token] (QR) · /receipt/[token] · /admin/* · /kitchen
│   ├── src/components/     ui.tsx, dish-art, customer/*, admin/*   └── src/lib/  api, format, customer hooks
│   └── e2e/                Playwright
└── docs/
```

## Boundaries and data flow
- **Browser → Next.js → `/api/v1` rewrite → FastAPI.** The proxy keeps the httpOnly auth cookie same-origin.
- **Routers are thin**; rules live in `services/`. Routers never compute prices, availability or payment state.
- **One availability engine** (`services/availability.py`) is called by menu display, recommendations, cart/order
  validation and order submission, so the screen and the server can't disagree.
- **Money** is integer minor units (paise). `services/billing.py` is the only place totals are computed.
- **Order tickets / table sessions / bills / payments / receipts / notification jobs** are separate tables, linked by ids.
- **Payment state changes only through `sessions.handle_payment_event`**: verify signature → de-duplicate by
  `(provider, event_id)` → reconcile amount/currency against payment and bill → apply in one transaction.
- **Concurrency**: `lock_row` (`SELECT … FOR UPDATE` on Postgres; process lock on SQLite) around order placement, payment
  creation and event handling; unique constraints `(session_id, ticket_seq)`, `(session_id, idempotency_key)`,
  `(provider, event_id)`, `(receipt_id, channel)` are the backstop.
- **Tenant isolation**: every admin route resolves the caller's membership for the target restaurant (`deps.access_for`);
  non-members get 404. Resource ids (order, item, rule, upload) are checked against the resource's own restaurant.
- **Notifications** run in an in-process worker (5 s poll, backoff 30 s/2 m/10 m/30 m, 5 attempts). Replace with a real queue for production.

## State machines
- Session: `open → bill_requested → payment_pending → paid → closed` (payment failure: `payment_pending → bill_requested`; a new add-on while `bill_requested` returns it to `open`).
- Ticket: `submitted → accepted → preparing → ready → served`; `rejected` (before cooking), `cancelled` (manager+). No generic status PATCH.
- Payment: `pending → succeeded | failed | cancelled`; duplicate charge → `refund_pending`.
- Notification: `queued → sending → sent | retry_scheduled → … → failed`.
