# Project memory (durable lessons & conventions)

- Money is always integer paise; never floats. Totals only via `services/billing.compute_bill`.
- Never trust the client for price, availability, tax, payment state or restaurant id; re-derive server-side.
- "Verified" matters: diet/allergen/ingredient claims need `verified=true`; missing data ≠ safe. Filters exclude unverified dishes.
- All availability questions go through `services/availability.evaluate_item`.
- Payment status changes only inside `sessions.handle_payment_event` (verify → dedupe → reconcile → apply). Flush before counting rows that you just changed (autoflush is off).
- `lock_row` uses `populate_existing()`: SQLAlchemy's identity map otherwise returns a stale locked row (caused duplicate ticket numbers under concurrency).
- Public `/restaurants/{slug}` also resolves ids → don't add another GET with the same shape (admin uses `/settings`).
- Mock providers must stay visibly labelled "simulated" in API data and UI.
- Next.js here is v16 with a different default config (cacheComponents); pages are client components, API proxied via rewrites.
- A port-8000 process unrelated to this project may exist on the dev machine; API runs on 8010.
