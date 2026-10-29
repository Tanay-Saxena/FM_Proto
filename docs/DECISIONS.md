# Decisions

| ID | Decision | Why / alternatives |
|---|---|---|
| D-001 | **SQLite by default, PostgreSQL supported** via `DATABASE_URL`. | No Docker/Postgres on the dev machine; SQLAlchemy+Alembic keep Postgres a config change. Row locks (`FOR UPDATE`) are used on Postgres; SQLite uses an in-process lock (single-process only). Production must use Postgres. |
| D-002 | **Payment provider: undecided.** Only `MockPaymentProvider` ships. | A real India UPI gateway (Razorpay, Cashfree, PhonePe PG…) needs merchant onboarding + sandbox credentials. The adapter interface and signed-webhook path are real. Static UPI QR rejected: no reliable automatic verification. |
| D-003 | SMS/email: mock log providers; real providers undecided (e.g. MSG91/Twilio, SES/Resend). | Mock sends are flagged `simulated` and never shown as delivered. |
| D-004 | **Hosting undecided** (Railway vs GCP). | Decide after local validation: needs Postgres, object storage (local disk is not durable), a worker, secrets. |
| D-005 | UI built on Radix Dialog + hand-built primitives, not shadcn CLI. | Small primitive set; avoids generated boilerplate. Single system, no competing UI frameworks. |
| D-006 | Dish attributes/allergens/ingredients/modifiers stored as JSON on `menu_items`. | Simpler than 5 tables at prototype scale; each attribute carries `source` + `verified`. Normalise if cross-dish querying is needed. |
| D-007 | **Availability precedence** (see `services/availability.py` docstring): hidden/archived → paused → sold-out/stock 0 → restaurant not accepting → per level (restaurant→category→item): block exception → allow exception (overrides weekly) → weekly/season rules → unconstrained. Start inclusive, end exclusive, overnight windows belong to the start day, evaluated in restaurant-local wall-clock time. | Deterministic, testable, matches spec §4. |
| D-008 | Recommendations are deterministic: hard filters (availability, budget, **verified** diet, **verified** allergen safety, admin opt-out) → preference score → admin boost clamped to ±5 → stable sort. No vector search. | Explainable; boosts can't violate constraints. Unverified data is excluded, never guessed. |
| D-009 | Billing: service charge on subtotal; tax on subtotal+service (or extracted when prices are tax-inclusive); half-up rounding; optional round-to-rupee. Rejected/cancelled tickets never billable. Discounts not implemented. | Exact integer maths. |
| D-010 | Scanning a table QR joins the table's **live** session (open/bill_requested/payment_pending) or opens a new one. | Physical presence at the table = access, standard for dine-in QR; unrelated tables/sessions stay inaccessible (unguessable 24-byte tokens). Paid/closed sessions are never rejoined. |
| D-011 | Payment-first checkout: bill can be requested/paid while tickets are still cooking; `payment_pending` locks ordering. A failed/cancelled payment returns to `bill_requested`. Staff can release a stuck lock (audited). | Matches spec M12 default policy; restaurant can opt to lock on bill request. |
| D-012 | Price/availability edits to the **live** menu apply immediately (audited); structural changes and imports go through draft → publish. Imports clone the live menu and upsert approved dishes, never delete. | Operational speed vs. safe publishing. |
| D-013 | Auth: scrypt passwords, HMAC-signed httpOnly SameSite=Lax cookie via same-origin proxy. | No third-party deps; CSRF mitigated by SameSite + JSON-only mutations. Add CSRF tokens/rotation for production. |
| D-014 | Demo clock (`X-Demo-Time`) honoured only when `DEMO_MODE=true`. | Lets demos show time-based availability; ignored in production. |
| D-015 | LLM optional (Anthropic adapter, untested against the live API). Allergen/ingredient/price/availability answers are always deterministic. | Safety facts must not come from a model. |
| D-016 | Reviews are built, but only a guest holding a paid receipt link can leave one (one per visit, none on refunded bills). Seeded reviews are flagged "sample". | Spec forbids fake reviews; the receipt link is the proof of a real visit. Supersedes the earlier "not built". |
| D-017 | Admin settings route is `GET /restaurants/{id}/settings` (not `/restaurants/{id}`). | The public `/restaurants/{slug}` route also resolves ids and would shadow it (bug found in e2e). |

| D-018 | Refunds are full-amount only, go through `PaymentProvider.refund`, owner-only, and mark the receipt. | Partial refunds need real gateway semantics to design properly. |
| D-019 | Photos are decoded and re-encoded to JPEG (≤1200px) and served only from `/media/dishes/…`. | Never serve uploaded bytes as sent; strips EXIF/GPS and non-image payloads. |
| D-020 | CSRF defence is an Origin allow-list on unsafe methods (cookie is SameSite=Lax + same-origin proxy). | No token plumbing needed for a same-origin app; requests with no Origin (webhooks, server-to-server) are unaffected. |
