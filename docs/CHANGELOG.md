# Changelog

## 2026-10-29 — Polish + prototype completion
- UI: animated landing, motion system (reveal, tilt, magnetic, count-up, confetti, fly-to-cart, haptics), collapsed hero on non-menu tabs, live order-status copy, receipt celebration, one-tap demo logins.
- New: dish photo upload, category/dish reordering, category rename/delete, reviews (guest form + owner inbox), full refunds (mock provider), move party / re-open table, guest split calculator, Origin check, contact-retention purge.
- Migration `e3f806f97da0` (reviews table, refund columns). Tests: 52 backend, 5 Playwright flows.

## 2026-10-28 — First working prototype
- Backend: models, availability engine, billing, recommender/chat, orders + add-on tickets, sessions/bills/payments (mock), receipts + PDF, notification worker, ingestion (PDF/OCR), RBAC admin API, kitchen API, seed data, Alembic baseline.
- Frontend: landing/demo hub, guest app (menu, discover/chat, table/bill/pay, receipt), owner dashboard (11 sections), kitchen display.
- Tests: 45 backend, 3 Playwright flows. Bugs found and fixed by tests: stale locked row under concurrency, failure-path pending-payment count before flush, admin settings route shadowed by public route.
