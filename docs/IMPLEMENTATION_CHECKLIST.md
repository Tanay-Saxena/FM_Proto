# Implementation checklist (as of 2026-10-28)

Legend: `[x]` implemented and tested · `[~]` partial / mocked · `[ ]` not built · `[!]` blocked.
Evidence = automated tests unless noted. Backend: `pytest` 45 passed. Browser: Playwright (2 flows + dashboard smoke) passed against the dev servers.

| Module | Status | Evidence / notes |
|---|---|---|
| M00 Repo & DX | [~] | README, `.env.example`, Alembic baseline (verified `upgrade head` on SQLite), docker-compose (Postgres, **not run** — no Docker here), `scripts/dev.sh`, health/ready endpoints, structured JSON logs + request ids. No linter/formatter configured. |
| M01 Design system | [~] | Tokens + Radix dialog/sheet, buttons, badges, forms, skeletons, empty/error states, reduced-motion CSS, focus rings. Screenshots reviewed at 390 px and desktop. No automated a11y audit run. |
| M02 Tenancy & config | [x] | 3 restaurants, per-restaurant theme tokens (validated hex/enum), tax/service/ordering policy/features/templates editable in UI. `test_h_*`. |
| M03 Customer QR menu | [x] | QR→table→session, categories, search, filters, dish sheet, provenance label, skeletons, deep links `/r/slug`, `/t/token`. `test_a_*`, e2e. Real photos not supported (illustrations only). |
| M04 Menu admin | [x] | Login, RBAC, inline price/state, bulk actions, item editor (diet, allergens, modifiers), **real dish photo upload** (decoded + re-encoded, EXIF stripped, ≤1200px, ≤5 MB), **category reorder / rename / delete-when-empty and dish reorder**, draft→publish, audit log. Not built: preview-a-draft-as-a-guest screen. `test_extras.py`, `extras.spec.ts`. |
| M05 PDF/image ingestion | [x] | Signature sniffing, size/page limits, text PDF + Tesseract OCR (incl. scanned PDFs via embedded images), flags (missing/ambiguous/duplicate/low-confidence/outlier), editable review, bulk approve, draft-only approval, retry; failed job leaves live menu untouched. `test_ingestion.py` (6). Heuristic parser — no LLM extraction. |
| M06 AI discovery | [~] | Deterministic recommender, NL parsing, verified-only diet/allergen filters, Surprise me, grounded chat, optional Anthropic adapter. `test_d_*`. **LLM path not tested against live API.** Weather is a client-supplied optional signal (no weather API). |
| M07 Availability engine | [x] | `test_availability.py` (12): boundaries, weekday, overnight, DST, season, exceptions, precedence; `test_c_*` API parity. Date-range exceptions are inclusive. |
| M08 Ranking controls | [x] | Boost/demote ±5, featured/labels, date range, never-recommend; try-ranking panel. Impressions/clicks tracked. `test_d_boost…`. |
| M09 Tables/QR/sessions | [x] | Tables, QR SVG, rotate, session lifecycle, release lock, audited close, **move a party to another table**, **re-open a table closed by mistake** (never a paid one). Counter-service mode **not built**. |
| M10 Orders & KDS | [x] | Server pricing, snapshots, idempotency, state machine, KDS with polling (3 s), sound, timers. `test_e_*`, `test_i_*`, e2e. Polling only (no SSE/WebSocket). |
| M11 Add-on orders | [x] | Distinct tickets, original untouched, same bill, concurrency test (8 parallel). Found+fixed a stale-row race. |
| M12 Bill & pay | [~] | Server bill, request bill, payment lock, failure recovery, double-pay protection, guest-side **split calculator** (one payment; it only shows each share). True split/partial payments and discounts **not built**. |
| M13 Payments | [~] | `PaymentProvider` interface, **mock only**, signed+deduped webhook, amount reconciliation, duplicate-charge flag, **full refunds through the provider adapter** (owner only, reason required, audited, receipt marked refunded; mock provider). **No real UPI gateway.** Partial refunds not built. `test_f_*`, `test_extras.py`. |
| M14 Receipts & notifications | [~] | Receipt (token, expiry, revoke, PDF), SMS/email jobs, retry/backoff, manual retry, masked recipients, templates. **Mock providers only**, flagged simulated. Retention purge job not written (documented in RUNBOOK). `test_g_*`. |
| M15 Reviews & analytics | [x] | Analytics dashboard (orders/day, hours, top dishes, engagement) with demo-data label. **Reviews**: one per paid receipt, only via the receipt link, blocked on refunded bills, owner inbox with average + distribution; sample reviews flagged "sample". |
| M16 Hardening | [~] | Tenant isolation, RBAC, upload, webhook, concurrency tests pass. **Origin check (CSRF defence) on cookie-authenticated writes**, **automated contact-retention purge** (hourly + `python -m app.retention`, default 180 days). No load test, no security scan, in-memory rate limiter (single process). Not deployed. |

## Definition of done (spec §14)
- [x] QR opens correct restaurant/table · [x] owner edits prices/availability · [x] schedules/exceptions/overrides
- [x] promote/demote within constraints · [x] PDF/image import→review→publish · [x] grounded AI (deterministic; LLM untested)
- [x] table orders · [x] kitchen progress · [x] add-ons · [x] separate tickets on one bill · [x] server totals
- [~] mock checkout success/failure/duplicates · [~] receipts + mock notifications · [x] isolation/upload/auth tests
- [x] reproducible local setup (verified from scripts on this machine) · [x] limitations documented (README, here, DECISIONS)

## Known limitations before any pilot
Simulated payments/refunds/SMS/email; SQLite default (single process); local-disk uploads (not durable in a container);
no true split payments or discounts; no counter-service mode; no draft-preview screen; polling KDS; heuristic menu parser;
in-memory rate limits; no load test or security scan.

## Next
The prototype is feature-complete. What remains is outside the code: **(1)** real payment gateway + SMS/email provider
(adapters sit behind `PaymentProvider` / messaging interfaces; needs merchant onboarding + sandbox keys), **(2)** printing and placing
the real table QR codes (SVGs come from Admin → Tables & QR), **(3)** deployment (Postgres, object storage for `storage/`, HTTPS,
`COOKIE_SECURE=true`, strong `SECRET_KEY`, `DEMO_MODE=false`, shared rate-limit store, run `alembic upgrade head`).
