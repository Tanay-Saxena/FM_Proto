# API (v1) — base `/api/v1`. Interactive reference: `/docs` (OpenAPI) on the API server.

Errors: `{"error": {"code", "message", "detail"}}`. Auth: httpOnly cookie `fm_session` (or `Authorization: Bearer`).
Guest endpoints need no account; table endpoints are scoped by an unguessable **session token**.
`X-Demo-Time` (ISO UTC) is honoured only when `DEMO_MODE=true`.

## Guest
| Method & path | Purpose |
|---|---|
| GET `/restaurants/{slug}` · `/restaurants/{slug}/menu` · `/menu-items/{id}` | profile+theme+open status · menu with live availability · one dish |
| POST `/restaurants/{ref}/recommendations` · `/random-dish` · `/chat` | ranked eligible dishes · Surprise me · grounded Q&A (rate-limited) |
| GET `/qr/{token}` · POST `/qr/{token}/session` | resolve table QR · join/open table session → `session_token` |
| GET `/table-sessions/{tok}` | state, tickets, live bill, payment, receipt token |
| POST `/table-sessions/{tok}/contact` · `/orders` · `/bill-request` · `/payment-session` | contact+consent · place original/add-on ticket (idempotency key) · request bill · create payment |
| GET `/table-sessions/{tok}/orders` · `/bill` · `/payments/{id}` | |
| POST `/table-sessions/{tok}/payments/{id}/simulate` | **demo only**: plays the provider by sending a signed event through the webhook handler |
| GET `/receipts/{token}` · `/receipts/{token}/pdf` | public receipt (no phone/email) |
| POST `/analytics/events` · GET `/demo/directory` (demo only) | |

## Auth
POST `/auth/login` · `/auth/logout` · GET `/auth/me`

## Restaurant admin (membership + permission enforced server-side; non-members get 404)
`GET/PATCH /restaurants/{id}/settings|(patch on /restaurants/{id})` · `GET /dashboard` · `/analytics` · `/audit` · `/staff` (+POST/DELETE) ·
`/menus` (+ `/{menu}`, `/{menu}/clone`, `/{menu}/publish`, `/{menu}/categories`, `/{menu}/items`) · `PATCH /items/{id}`, `POST /items/bulk`, `PATCH /categories/{id}` ·
`/availability-rules` (+PATCH/DELETE) · `/recommendation-rules` (+PATCH/DELETE) · `/tables` (+POST, `/tables/{id}/qr-codes`, `/qr-codes/{id}/image.svg`) ·
`/orders`, `/sessions` (+`/sessions/{id}/action`: release_lock | close | force_close) · `/payments`, `/notifications`, `POST /receipts/{id}/revoke` ·
`/menu-uploads` (multipart), `/ingestion-jobs` (+`/{id}/process|candidates|bulk|approve`), `PATCH /ingestion-candidates/{id}`.

## Kitchen
GET `/restaurants/{id}/kitchen/queue` · `/kitchen/events?since=` · POST `/orders/{id}/status-transition` · `/orders/{id}/acknowledge` · `/orders/{id}/pos-sync` (simulated)

## Webhooks / platform
POST `/webhooks/payments/{provider}` (signature header `x-mock-signature` for the mock) · POST `/notifications/{id}/retry` ·
GET `/platform/restaurants` · `/platform/health` (platform admins; no tenant data).

Not implemented from the original spec: `POST /restaurants` UI (endpoint exists, platform admin only), `/webhooks/pos/{provider}`, refunds, counter mode.
