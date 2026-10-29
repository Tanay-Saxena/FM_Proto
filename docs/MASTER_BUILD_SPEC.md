# Restaurant AI Food Discovery & Table Ordering Platform
## Master Product Requirements + Cloud Code Build Prompt

**Document version:** 1.1  
**Status:** Approved product direction for prototype planning  
**Initial runtime:** Local development  
**Target deployment later:** Railway or Google Cloud Platform, selected after local validation  
**Product type:** Multi-tenant restaurant SaaS with QR menus, AI food discovery, live availability, kitchen order management, split/order-session lifecycle, UPI-ready checkout and digital receipts.

---

# HOW TO USE THIS DOCUMENT

This file is the product source of truth and the master build prompt for Cloud Code.

1. Save this file in the repository as `docs/MASTER_BUILD_SPEC.md`.
2. Open the repository in Cloud Code.
3. Paste the **Cloud Code master instruction** near the end of this document.
4. Build the product one module at a time. Do not ask the coding agent to generate the entire application in one pass.
5. Require the agent to update `docs/IMPLEMENTATION_CHECKLIST.md`, tests, and documentation after every module.
6. Keep payment and messaging integrations in sandbox/mock mode until the provider, credentials, webhook configuration, and production requirements have been reviewed.

The objective is a polished, interactive, extensible prototype with production-minded foundations. A prototype is not automatically production-ready merely because it runs locally.

---

# 1. PRODUCT VISION

Build a **highly customizable, AI-powered restaurant menu, food discovery, table ordering, kitchen operations and digital billing platform**.

Customers scan a QR code at a table or restaurant counter. They can explore the menu, ask AI about dishes, get recommendations, add items to an order, send the order to the kitchen, continue adding items while the table session remains open, and pay the final bill using an available payment method such as UPI. After successful payment, the system provides a digital receipt link and sends a notification through configured channels.

Restaurant owners and authorized staff manage the entire experience through the application. The product must not require the developer to manually change menu data, prices, item availability, schedules, recommendations, branding, or restaurant configuration in code.

## Core promise

**Scan. Discover. Order. Add more. Pay.**

For restaurant operators: **Upload. Configure. Manage. Serve. Reconcile.**

## Product principles

- Restaurant configuration must be data-driven, not hardcoded.
- Customer browsing should not require an app installation.
- The restaurant's approved menu is the source of truth.
- AI can help explain and rank menu items but must not invent items, prices, ingredients, availability, allergens, or order status.
- The restaurant controls prices, availability schedules, promotions, menu ordering, and recommendation boosts from its dashboard.
- Orders must be traceable to restaurant, table, customer/session, and kitchen workflow.
- An order sent to the kitchen can receive additional items later while the table's service session is open.
- The bill is calculated by the server from the complete table/session order ledger.
- Payment success must be verified server-side through the payment provider; a client-side screen is not proof of payment.
- The product should look premium and feel fast, accessible, and intuitive across cafés, bars, casual dining, fine dining, quick-service restaurants, bakeries, food courts and multi-cuisine venues.
- Use mock/demo data to make the prototype useful before real restaurants and integrations are connected.
- Keep clear boundaries between demo functionality and live integrations.

---

# 2. USERS AND ROLES

## 2.1 Customer

Can:
- Open a menu from a QR code.
- Browse categories, search and filter.
- View dish descriptions, images, price, taste, spice, texture and verified dietary details.
- Ask AI questions about the restaurant's menu.
- Get mood-, taste-, budget- and optionally weather/season-aware recommendations.
- Use “Surprise me” to choose an eligible dish.
- Add dishes and supported modifiers to an order.
- Submit an order to the restaurant/kitchen.
- Add more items to the same open table/service session.
- View order progress and the running bill.
- Enter their name, mobile number and email when required for the order/receipt flow.
- Pay the final bill using the configured checkout option.
- Open the digital receipt through a secure link.

Customer browsing should work without creating a platform account. Collect only customer information required for ordering, service and receipt delivery.

## 2.2 Restaurant owner / manager

Can, through the admin dashboard:
- Manage restaurant profile, branding, cuisine, location, currency, tax and service-charge settings.
- Configure menus, categories, items, modifiers and photos.
- Upload PDF/image menus and review extracted information.
- Edit prices without developer involvement.
- Configure availability windows, weekdays, dates, time ranges, inventory/stock limits and sold-out status.
- Schedule temporary or seasonal menus.
- Configure item/category display order and recommendation priority.
- Boost or demote dishes in recommendations.
- Mark an item unavailable, sold out, paused, hidden or available only during selected periods.
- Manage table numbers, QR codes and table status.
- See incoming orders, table/session details, order history and payment status.
- Manage staff permissions.
- Review basic analytics and audit history.

## 2.3 Kitchen staff

Can:
- Access a kitchen display/queue restricted to the relevant restaurant.
- See new orders with table number, order number, time, item names, quantities, modifiers and relevant notes.
- Accept/acknowledge an order.
- Move items/orders through configured statuses such as `received`, `accepted`, `preparing`, `ready`, `served` or `cancelled`, subject to permissions.
- See **additional items** appended to an already active table session as a clearly identifiable new order/add-on ticket.
- See timestamps and distinguish new items from previously submitted items.
- Avoid accidentally treating a customer’s new item as a replacement for an already prepared item.

Kitchen staff should not be able to change payment records, provider settings, tenant ownership or sensitive restaurant configuration unless explicitly granted that permission.

## 2.4 Platform administrator

Can:
- Manage restaurant onboarding and platform configuration.
- Inspect operational errors and ingestion failures.
- Manage platform-level settings and feature flags.
- View audit events and integration health with appropriate authorization.
- Access tenant data only through explicit, permission-controlled administrative workflows.

## 2.5 Authorization

Use role-based access control and enforce authorization in the backend, not only by hiding UI elements. Every protected restaurant resource must be scoped to the authenticated user’s authorized restaurant membership.

---

# 3. PRODUCT MODULES AND CHECKLIST

Track each module in `docs/IMPLEMENTATION_CHECKLIST.md` using:
- `[ ] Not started`
- `[-] In progress`
- `[x] Implemented and tested`
- `[!] Blocked`

A module is not complete until implementation, tests, documentation and acceptance criteria are reviewed.

## M00 — Repository, architecture and developer experience

- [ ] Inspect repository and current dependencies before making changes.
- [ ] Create monorepo or clearly separated frontend/backend folders.
- [ ] Add `.gitignore`, `.env.example`, README and architecture docs.
- [ ] Add Docker Compose for local PostgreSQL and any required worker/cache.
- [ ] Add health checks, structured logging, linting, formatting and test commands.
- [ ] Add migration workflow and seed-data command.
- [ ] Add a checklist that tracks every module.
- [ ] Document local setup from a clean checkout.
- [ ] Never commit credentials, real customer information, payment secrets or uploaded private files.

**Acceptance:** A new developer can follow the README and run the application locally with seeded demo data.

## M01 — Design system and premium UI foundation

- [ ] Create a coherent design system with configurable themes.
- [ ] Use a polished component library rather than hand-building every primitive.
- [ ] Build responsive navigation, cards, dialogs, sheets, forms, tables, badges, tabs, skeletons, toasts, empty states and error states.
- [ ] Add accessible keyboard/focus behavior and semantic HTML.
- [ ] Add loading, success, error and disabled states for every important action.
- [ ] Add motion sparingly and respect reduced-motion preferences.
- [ ] Create reusable restaurant, menu, dish, order and dashboard components.
- [ ] Avoid generic template-looking pages; establish a consistent visual identity.

**Acceptance:** The product looks intentional, premium and usable on mobile and desktop, not like an unstyled CRUD scaffold.

## M02 — Restaurant tenancy, profile and configuration

- [ ] Create restaurant records and unique public slugs.
- [ ] Support restaurant-specific branding, logo, accent colors and typography/theme tokens.
- [ ] Support restaurant type/cuisine configuration.
- [ ] Support timezone, currency and locale.
- [ ] Support tax/service-charge configuration with clear display rules.
- [ ] Support feature flags for optional modules such as reviews, AI, ordering and weather suggestions.
- [ ] Support multiple restaurants without sharing protected data.
- [ ] Seed demo restaurants representing different venue types.

**Acceptance:** Different restaurants can have distinct menus, themes, settings and users without code changes.

## M03 — Customer QR menu and discovery UI

- [ ] Create restaurant landing page and category navigation.
- [ ] Create search, sorting and filter controls.
- [ ] Create dish cards and detail views.
- [ ] Show current price and availability status.
- [ ] Support photos, image placeholders and explicit image provenance.
- [ ] Support mobile-first layouts, empty states and loading skeletons.
- [ ] Support direct links to restaurant/menu/dish.
- [ ] Create QR codes for restaurant and table destinations.
- [ ] Keep QR destinations stable when menu contents change.
- [ ] Make menu browsing usable without sign-in.

**Acceptance:** Scanning a table QR opens the correct restaurant and table context, and displays only that restaurant’s published menu.

## M04 — Menu administration and customization

- [ ] Build owner/manager login and protected dashboard.
- [ ] Add/edit/archive categories and items.
- [ ] Edit prices, descriptions, images, modifiers and item attributes.
- [ ] Bulk edit item availability and display order.
- [ ] Support draft, published and archived menu states.
- [ ] Preview changes before publishing.
- [ ] Preserve published data until an approved update is published.
- [ ] Allow restaurant staff to manage items within their assigned permissions.
- [ ] Track significant changes in an audit log.

**Acceptance:** An authorized owner can manage menu content and pricing from the UI without changing source code or redeploying the app.

## M05 — PDF/image menu ingestion

- [ ] Upload PDF, JPEG, PNG and WebP within configurable limits.
- [ ] Validate file signatures and content types; do not trust extensions alone.
- [ ] Extract selectable PDF text; use OCR for scanned PDFs and images.
- [ ] Detect categories, item names, descriptions and prices.
- [ ] Return structured, schema-validated extraction results.
- [ ] Track source file, page/region where practical, confidence and processing errors.
- [ ] Flag ambiguous prices, duplicate items and uncertain fields.
- [ ] Provide an editable owner review screen and bulk correction.
- [ ] Require approval before publishing extracted content.
- [ ] Support retrying failed jobs.
- [ ] Ensure failed processing never replaces the current live menu.
- [ ] Avoid inventing ingredients, allergens, dietary status or prices.

**Acceptance:** A sample text PDF and a scanned image can be uploaded, parsed, reviewed, corrected and published through the dashboard.

## M06 — Dish intelligence and AI food discovery

- [ ] Define structured taste, flavor, spice, texture and dietary attributes.
- [ ] Track whether attributes are restaurant-confirmed, source-derived or AI-suggested.
- [ ] Add preference chips and natural-language preference input.
- [ ] Implement hard filtering for current availability, price limits and verified dietary constraints.
- [ ] Implement deterministic, explainable ranking before adding unnecessary vector search.
- [ ] Add recommendation boosts/demotions controlled by restaurant admins.
- [ ] Add “Surprise me” with the same eligibility rules as recommendations.
- [ ] Add ask-a-dish chat grounded in the selected restaurant’s current menu.
- [ ] Validate all dish IDs returned by the AI.
- [ ] Respond safely when the menu lacks an answer.
- [ ] Add model provider abstraction, usage limits, timeout handling and tests.
- [ ] Add optional weather/season signals as configurable ranking inputs, not mandatory dependencies.

**Acceptance:** AI recommendations never return dishes from another restaurant or recommend an unavailable item as orderable. Admin-defined boosts affect ranking predictably without overriding hard constraints.

## M07 — Availability rules and scheduling engine

This module is essential. Availability must be data-driven and editable by authorized restaurant staff.

- [ ] Support item-level and category-level availability.
- [ ] Support states such as `available`, `paused`, `sold_out`, `hidden` and `scheduled`.
- [ ] Support weekly schedules: day of week and local start/end times.
- [ ] Support date-specific exceptions, holidays and temporary closures.
- [ ] Support start/end dates for seasonal menus or limited-time items.
- [ ] Support optional quantity/stock limits.
- [ ] Support time slots such as breakfast, lunch, dinner, happy hour or custom periods.
- [ ] Support restaurant-specific timezone and daylight-saving behavior where applicable.
- [ ] Define precedence for conflicts: explicit sold-out/paused status and date exceptions must be resolved deterministically before normal weekly schedules.
- [ ] Expose current availability through a shared domain service used by menu display, recommendations, cart validation and order submission.
- [ ] Revalidate availability on the server immediately before order placement.
- [ ] Display next availability or “not currently available” where it can be calculated reliably.
- [ ] Let authorized admins configure schedules from a friendly UI.
- [ ] Store changes with actor and timestamp in audit history.

**Acceptance:** A dish scheduled for 12:00–15:00 in the restaurant’s timezone is shown as orderable only during its configured availability window, unless a higher-priority override makes it unavailable.

## M08 — Recommendation ranking controls for admins

- [ ] Admin can set recommendation boost, neutral or demotion for a dish/category.
- [ ] Admin can configure featured dishes and promotional collections.
- [ ] Optional schedule dates can activate/deactivate a boost.
- [ ] Hard eligibility constraints always run before ranking boosts.
- [ ] Do not mislabel a promoted item as “most popular” unless actual metrics support that claim.
- [ ] Track recommendation impressions and selections using privacy-conscious event data.
- [ ] Explain admin controls in the dashboard.

**Acceptance:** An admin can promote or demote a dish without a developer changing code, while price, availability and dietary constraints still apply.

## M09 — Table, QR and service-session management

- [ ] Manage table numbers and optional zones/sections.
- [ ] Generate unique QR destinations for each table.
- [ ] Resolve QR to restaurant + table context on the server.
- [ ] Support table/session lifecycle such as `open`, `bill_requested`, `payment_pending`, `paid` and `closed`.
- [ ] Define who may open, reopen, transfer or close a session.
- [ ] Prevent customers from accessing another table’s private order or receipt.
- [ ] Use unguessable public session tokens or secure capabilities; never rely on a sequential table number as authorization.
- [ ] Support a counter/service mode if enabled by restaurant configuration.
- [ ] Keep an audit trail for session changes.

**Acceptance:** An order is associated with the correct restaurant and table, and the customer sees only the session they are authorized to access.

## M10 — Order placement and kitchen display system (KDS)

- [ ] Create a cart that supports quantities, modifiers and notes.
- [ ] Collect customer name, mobile number and email at the appropriate point before order placement/receipt delivery.
- [ ] Validate contact data and explain why it is collected.
- [ ] Recalculate item prices, discounts, tax, fees and totals on the backend.
- [ ] Store order-item price/name snapshots.
- [ ] Submit a new order to the restaurant's kitchen queue.
- [ ] Show order number, table number, timestamp, items, quantities, modifiers and notes.
- [ ] Implement kitchen statuses and permitted transitions.
- [ ] Provide a dedicated, readable KDS view suitable for a kitchen display/tablet.
- [ ] Use polling or a transport abstraction for live updates; prefer WebSockets/SSE only when properly implemented and tested.
- [ ] Handle duplicate submissions idempotently.
- [ ] Revalidate availability and current price at submission.
- [ ] Define cancellation, rejection and unavailable-after-submission workflows.

**Acceptance:** When a customer confirms an order, the kitchen view displays the correct table and order details without manual developer intervention.

## M11 — Add-on orders while food is being prepared

This is a core requirement, not a future nice-to-have.

- [ ] Keep a table/service session open until the bill is paid and the session is closed by the configured workflow.
- [ ] Allow additional items to be selected while an earlier order is `received`, `accepted`, `preparing` or `ready`, subject to restaurant policy.
- [ ] Create a distinct add-on order/ticket linked to the same service session.
- [ ] Send the add-on ticket to the kitchen queue.
- [ ] Clearly mark it as an additional order and show its own timestamp and order/ticket number.
- [ ] Do not mutate or erase the original kitchen ticket.
- [ ] Add the new items to the session’s running bill.
- [ ] Revalidate availability, price, session state and restaurant rules on the server.
- [ ] Prevent new items after the session is closed or payment finalization has locked it, unless an authorized reopen workflow exists.
- [ ] Ensure two concurrent add-on requests do not lose items or corrupt totals.
- [ ] Provide UI feedback that the additional order has been submitted and show its status.

**Acceptance scenario:** A customer at Table 12 submits two items. The kitchen receives Order A. While it is preparing, the customer adds a dessert. The kitchen receives Add-on Order B for Table 12. Both orders remain visible, and the dessert is included in the table’s final bill.

## M12 — Running bill and bill-pay flow

- [ ] Provide a session summary of all order tickets and line items.
- [ ] Clearly distinguish ordered, cancelled, rejected and billable items.
- [ ] Define how taxes, service charges, discounts and rounding are applied.
- [ ] Recalculate the bill on the server from authoritative order records.
- [ ] Show the current total and itemized bill.
- [ ] Provide a “Request bill” or “Pay bill” action according to restaurant configuration.
- [ ] Atomically lock new ordering or enter a payment-pending state when final checkout starts, according to configured policy.
- [ ] Handle payment failure by safely restoring the session to an appropriate open/payable state.
- [ ] Prevent double payment and duplicate order creation.
- [ ] Allow staff to resolve exceptional cases using audited actions.
- [ ] Define support for partial/split bills as a configurable future capability; do not imply it exists unless implemented and tested.

**Acceptance:** The final bill includes every valid order and add-on in the session exactly once. After a verified successful payment, the session can be closed and a receipt generated.

## M13 — UPI/payment integration

Build a provider adapter; do not hardcode payment-provider assumptions into order logic.

- [ ] Define `PaymentProvider` interface.
- [ ] Implement `MockPaymentProvider` for local development.
- [ ] Model payment intent/session, pending/success/failure/cancelled/refunded states.
- [ ] Integrate a selected provider's official sandbox after credentials are supplied.
- [ ] For India, choose a payment gateway that supports the required UPI flow and merchant onboarding.
- [ ] Do not assume a generic static UPI QR guarantees reliable automatic payment verification.
- [ ] Verify webhook signatures and provider event authenticity.
- [ ] Use idempotency keys and deduplicate provider events.
- [ ] Reconcile payment amount, currency, order/session ID and provider reference.
- [ ] Never mark a bill paid from a frontend redirect alone.
- [ ] Never store raw card details or UPI PINs.
- [ ] Keep secrets out of source control.
- [ ] Implement refunds only through explicit authorized provider workflows.
- [ ] Add payment audit logs and a reconciliation view for authorized staff.

**Acceptance:** Local demo payments are clearly labelled simulated. In a real sandbox, only verified provider events can transition a payment to successful.

## M14 — Digital receipt and SMS/email notifications

The intended customer experience is to collect name, mobile number and email during order placement and deliver a receipt link after payment confirmation.

- [ ] Create a durable receipt record after verified successful payment.
- [ ] Include restaurant details, receipt/order number, table/session reference, itemized bill, tax/fees, total, currency, payment status and timestamp.
- [ ] Generate a secure, unguessable receipt URL with appropriate access controls and expiry/revocation policy.
- [ ] Do not expose sequential database IDs or sensitive customer data in public URLs.
- [ ] Send a receipt link by SMS to the supplied mobile number.
- [ ] Send the receipt link by email to the supplied email address when email delivery is configured.
- [ ] Use provider adapters such as `SmsProvider` and `EmailProvider`.
- [ ] Implement local mock/logging providers; do not claim an actual SMS/email was sent in mock mode.
- [ ] Retry transient failures with bounded backoff and idempotency.
- [ ] Track delivery status separately from payment/order status.
- [ ] Avoid putting sensitive information directly in SMS.
- [ ] Add opt-in/notice, retention and consent handling appropriate to the deployment and jurisdiction.
- [ ] Provide a staff/admin way to retry a failed notification.
- [ ] Keep notification templates customizable per restaurant and language.

**Acceptance:** After payment is verified, the receipt is generated once, and notification jobs are queued. The UI distinguishes “receipt ready”, “SMS sent/failed” and “email sent/failed” accurately.

## M15 — Reviews, analytics and reporting

- [ ] Provide configurable reviews/ratings only when the source is genuine.
- [ ] Do not generate fake reviews or ratings.
- [ ] Track menu views, dish views, recommendation clicks, add-to-cart and orders using privacy-conscious analytics.
- [ ] Show restaurant-level dashboards for orders, popular items, time windows and menu engagement.
- [ ] Label sample data as demo data.
- [ ] Restrict analytics to authorized restaurant members.

## M16 — Production hardening and deployment readiness

- [ ] Run frontend, backend, integration and end-to-end tests.
- [ ] Validate tenant isolation and role permissions.
- [ ] Test malformed uploads, OCR failures, oversized files and duplicate items.
- [ ] Test availability boundary times, timezone handling and overrides.
- [ ] Test concurrent add-on orders and final bill locking.
- [ ] Test duplicate payment webhooks and payment failure/retry.
- [ ] Test receipt/notification retries.
- [ ] Add health/readiness checks and structured logs.
- [ ] Add backup and migration instructions.
- [ ] Document environment variables and provider setup.
- [ ] Choose Railway or GCP only after assessing storage, worker, database, deployment and cost requirements.
- [ ] Use managed database and object storage for a production-like deployment; local disk should not be assumed durable in a cloud container.
- [ ] Document known limitations before any live pilot.

---

# 4. ADMIN AVAILABILITY AND RECOMMENDATION RULES

The admin dashboard must make operational changes possible without code changes or redeployment.

## Availability model

Support these dimensions:

1. **Manual state:** available, paused, sold out, hidden.
2. **Weekly schedule:** weekday and local time interval.
3. **Date exceptions:** special hours, holidays, one-off availability.
4. **Seasonal window:** start and end date/time.
5. **Stock limit:** optional remaining quantity.
6. **Category schedule:** e.g. breakfast category available only in the morning.
7. **Restaurant status:** open/closed or accepting/not accepting orders.
8. **Order policy:** allow/deny ordering outside service hours.

Define and document precedence. A recommended initial rule is:
- Disabled/hidden/archived items are never orderable.
- An explicit sold-out or paused override blocks ordering.
- Date-specific exceptions override the weekly schedule.
- A valid schedule window must be active.
- Optional stock must be sufficient.
- The final decision is made server-side at order submission.

Do not rely only on hiding an item in the frontend. Every order must be revalidated.

## Recommendation controls

Admin can configure:
- Featured item/category.
- Boost or demotion score.
- Active date range/time range.
- Promotion label and optional display priority.
- Whether an item can appear in recommendations.

Recommendation flow:
1. Load current published menu.
2. Apply hard eligibility filters (restaurant, availability, budget, verified dietary constraints).
3. Apply customer preference scoring.
4. Apply configured promotion/boost within a bounded range.
5. Return ranked eligible items.
6. Explain results using grounded menu attributes.

An admin boost must never make a sold-out item orderable or override a required dietary constraint.

---

# 5. ORDER AND TABLE SESSION STATE MODEL

Keep the **table service session**, **order tickets**, **payment** and **notification delivery** as separate but linked concepts.

## Suggested session states

- `open`
- `bill_requested`
- `payment_pending`
- `paid`
- `closed`
- `cancelled` (only where the business workflow allows it)

## Suggested order/ticket states

- `submitted`
- `accepted`
- `preparing`
- `ready`
- `served`
- `rejected`
- `cancelled`

Use explicit transition rules and permissions. Do not permit arbitrary status changes through generic PATCH endpoints.

## Suggested payment states

- `created`
- `pending`
- `succeeded`
- `failed`
- `cancelled`
- `refund_pending`
- `refunded`

## Suggested notification states

- `queued`
- `sending`
- `sent`
- `failed`
- `retry_scheduled`

## Core workflow

1. Table QR opens a restaurant/table context.
2. Customer enters contact details before first order submission.
3. Customer submits Order A.
4. Backend validates items and creates a session/order transactionally.
5. Kitchen receives Order A for that table.
6. Customer adds dessert or another item.
7. Backend creates Add-on Order B under the same session.
8. Kitchen receives Order B as a distinct ticket.
9. Both valid tickets contribute to the running bill.
10. Customer requests the final bill.
11. Backend locks or transitions the session to payment pending, following the defined policy.
12. Server calculates the final amount from authoritative records.
13. Payment provider handles checkout.
14. Verified payment webhook updates payment/session state idempotently.
15. Receipt is generated and notification jobs are queued.
16. SMS/email providers deliver the receipt link; delivery status is recorded.
17. Session is closed according to restaurant policy.

Use database transactions, constraints and idempotency to protect against double clicks, retries, webhook duplication and concurrent add-on requests.

---

# 6. DATA MODEL

Implement the schema through SQLAlchemy models and Alembic migrations. The list below is the minimum logical model; refine relationships and constraints during implementation.

## Restaurant and access

- `restaurants`: name, slug, status, timezone, currency, branding, configuration.
- `users`: identity and status.
- `restaurant_memberships`: user, restaurant, role and permissions.
- `restaurant_tables`: restaurant, table label/number, zone, status.
- `qr_codes`: restaurant, table, public destination token, active status.

## Menus

- `menus`: restaurant, name, version, draft/published/archived status.
- `menu_categories`: menu, name, order, optional schedule.
- `menu_items`: menu, category, name, description, price, currency, availability state.
- `item_attributes`: item, key/value, source, confidence, verification state.
- `item_ingredients`: item, ingredient and verification.
- `item_allergens`: item, allergen and verification.
- `item_images`: item, storage key, provenance and type.
- `item_modifiers` / `modifier_groups`: configurable add-ons and choices.
- `availability_rules`: target item/category/restaurant, schedule, timezone, date range, state and precedence.
- `inventory_records` (optional): item and stock/quantity controls.
- `recommendation_rules`: target, boost/demotion, schedule and active state.

## Ingestion

- `menu_uploads`: source file, restaurant, status and metadata.
- `ingestion_jobs`: upload, processing state, attempts, timestamps and errors.
- `ingestion_candidates`: extracted structured data, confidence and review state.
- `ingestion_field_sources`: optional source page/region and provenance.

## Customer sessions and ordering

- `table_sessions`: restaurant, table, secure public token reference, state, customer contact reference, opened/closed timestamps.
- `customers` or `order_contacts`: minimal name, phone and email fields needed for service/receipts, with retention policy.
- `orders`: restaurant, session, order number, ticket type, state, timestamps and idempotency key.
- `order_items`: order, menu item reference, item name/price snapshots, quantity and modifiers snapshot.
- `order_status_events`: order, old/new state, actor and timestamp.
- `bills` / `bill_snapshots`: session, calculated line items, fees, tax, total and version.
- `payments`: bill/session/order reference, provider, provider reference, amount, currency, state and idempotency metadata.
- `payment_events`: deduplicated provider events and verification result.
- `receipts`: secure receipt reference, bill snapshot, generated timestamp and access policy.
- `notification_jobs`: receipt, channel, recipient reference, state, attempt count and provider reference.
- `integration_events`: POS/provider delivery, external reference, status and retry information.

## Supporting data

- `reviews`: item, rating, content, moderation state and provenance.
- `analytics_events`: event type, restaurant, item/session references and timestamps.
- `audit_logs`: actor, restaurant, action, resource and timestamp.
- `feature_flags`: configurable features at platform or restaurant scope.

## Data integrity requirements

- Use UUIDs for internal IDs.
- Store money as integer minor units or exact Decimal values with explicit currency.
- Store historical item name and price snapshots on order lines.
- Apply foreign keys and indexes.
- Enforce tenant isolation in service queries and authorization.
- Avoid storing sensitive data that is not needed.
- Keep payment event IDs unique per provider.
- Use idempotency keys for order creation, payment operations and notification processing.
- Keep a published menu unchanged until a new version is explicitly published.
- Never infer “allergen-free” from missing allergen data.
- Avoid exposing sequential database IDs as authorization tokens.

---

# 7. API MODULES

Use a versioned REST API at `/api/v1`. Define Pydantic request/response models and publish OpenAPI documentation.

## Public/customer endpoints

- `GET /restaurants/{slug}`
- `GET /restaurants/{slug}/menu`
- `GET /menu-items/{item_id}`
- `POST /restaurants/{restaurant_id}/recommendations`
- `POST /restaurants/{restaurant_id}/chat`
- `POST /restaurants/{restaurant_id}/random-dish`
- `GET /table-sessions/{public_token}`
- `POST /table-sessions/{public_token}/contact`
- `POST /table-sessions/{public_token}/orders`
- `GET /table-sessions/{public_token}/orders`
- `POST /table-sessions/{public_token}/bill-request`
- `GET /table-sessions/{public_token}/bill`
- `POST /table-sessions/{public_token}/payment-session`
- `GET /receipts/{secure_receipt_token}`

Public session tokens must be unguessable and narrowly scoped. Validate that a token grants access only to the intended table session and permitted actions.

## Restaurant/admin endpoints

- `POST /auth/login`
- `POST /restaurants`
- `PATCH /restaurants/{restaurant_id}`
- `GET /restaurants/{restaurant_id}/dashboard`
- `POST /restaurants/{restaurant_id}/menu-uploads`
- `GET /menu-uploads/{upload_id}`
- `POST /menu-uploads/{upload_id}/process`
- `GET /ingestion-jobs/{job_id}/candidates`
- `PATCH /ingestion-candidates/{candidate_id}`
- `POST /ingestion-jobs/{job_id}/approve`
- `POST /menus/{menu_id}/publish`
- `POST /restaurants/{restaurant_id}/tables`
- `POST /restaurants/{restaurant_id}/qr-codes`
- `POST /restaurants/{restaurant_id}/availability-rules`
- `PATCH /availability-rules/{rule_id}`
- `POST /restaurants/{restaurant_id}/recommendation-rules`
- `PATCH /recommendation-rules/{rule_id}`
- `GET /restaurants/{restaurant_id}/orders`
- `GET /restaurants/{restaurant_id}/sessions`
- `POST /orders/{order_id}/status-transition`
- `POST /table-sessions/{session_id}/close`
- `GET /restaurants/{restaurant_id}/payments`
- `GET /restaurants/{restaurant_id}/notifications`

## Kitchen endpoints

- `GET /restaurants/{restaurant_id}/kitchen/queue`
- `POST /orders/{order_id}/acknowledge`
- `POST /orders/{order_id}/status-transition`
- `GET /restaurants/{restaurant_id}/kitchen/events`

## Webhooks and integrations

- `POST /webhooks/payments/{provider}`
- `POST /webhooks/pos/{provider}` where the provider supports inbound webhooks
- `POST /orders/{order_id}/pos-sync`
- `POST /notifications/{notification_id}/retry`

Use server-side authorization, schema validation, rate limiting, consistent errors, structured logs and audit events. Never trust client-submitted prices, tax, payment state, availability or restaurant ownership.

---

# 8. RECOMMENDED TECH STACK AND LIBRARIES

Choose stable, mutually compatible versions at implementation time. Inspect current package compatibility instead of blindly pinning obsolete versions.

## Frontend

- **Next.js App Router + TypeScript** for routing and application structure.
- **Tailwind CSS** for styling and design tokens.
- **shadcn/ui + Radix UI** for accessible, composable components.
- **Motion for React** (or a compatible animation library) for purposeful transitions.
- **Lucide** icons.
- **TanStack Query** for server-state caching and mutation workflows where appropriate.
- **React Hook Form + Zod** for forms and validation.
- **Recharts** for simple admin analytics.
- **Playwright** for end-to-end tests.

Use a single coherent component system. Avoid installing several competing UI frameworks. Keep animations fast and respect reduced-motion preferences.

## Backend

- **FastAPI + Pydantic** for typed REST APIs.
- **SQLAlchemy + Alembic** for persistence and migrations.
- **PostgreSQL** for relational records and transactional workflows.
- **Redis and a worker queue** if needed for ingestion and notifications; choose a queue with retries and clear job states. Keep the local setup understandable.
- **Pytest** for unit/integration tests.
- **Structured logging** and request IDs.
- Provider interfaces for LLM, OCR, storage, payment, POS, SMS and email.

## Files and AI

- PDF text extraction library for selectable-text PDFs.
- OCR engine for scanned documents and menu images.
- Schema-constrained LLM output for ambiguous extraction/enrichment tasks.
- A configurable model provider adapter.
- Local object-storage abstraction for prototype; cloud object storage for deployment.
- Image processing/resizing with safe limits.

Do not introduce vector databases, multi-agent orchestration or microservices unless measurable needs justify them. The first recommendation engine should use structured filtering and deterministic ranking.

---

# 9. PREMIUM UI/UX REQUIREMENTS

The product must be visually polished and highly customizable. Avoid a generic admin template or a plain list of CRUD tables.

## Customer experience

- Mobile-first layout designed for one-handed use.
- Premium restaurant hero section with branding and relevant imagery.
- Attractive dish cards with consistent aspect ratios, price, availability and key flavor tags.
- Search that is easy to reach.
- Clear category navigation.
- Filters presented as chips, sheets or a compact filter panel.
- Dish detail modal/page with readable information and clear actions.
- Persistent but unobtrusive cart/session summary when ordering is enabled.
- Clear distinction between “Add to order”, “Order submitted”, “Preparing”, “Ready” and “Paid”.
- Accessible contrast, readable type, large tap targets and appropriate spacing.
- Skeleton loading, useful empty states and clear error recovery.
- Tasteful motion, subtle transitions and interactive feedback.
- Avoid unnecessary animations, oversized gradients, excessive glassmorphism or distracting effects.

## Restaurant dashboard

- A polished application shell with sidebar/navigation, breadcrumbs and clear page hierarchy.
- Dashboard summary cards for orders, active tables, pending kitchen tickets and ingestion jobs.
- Menu editor with search, bulk actions, drag/reorder where appropriate and responsive detail panels.
- Schedule editor with weekday/time windows and date exceptions.
- Availability indicators and fast “mark sold out” actions.
- Recommendation controls with boost/demotion and active schedule.
- Kitchen display with high readability, large status controls and new-ticket emphasis.
- Order detail with table, customer-provided name where appropriate, item details and timeline.
- Payment/receipt status indicators that distinguish provider status from notification delivery status.
- Confirmation dialogs for destructive actions and important state transitions.

## Customization system

Support restaurant-level configuration for:
- Logo and branding.
- Theme/accent colors and selected theme presets.
- Menu layout/card density where appropriate.
- Cuisine and category configuration.
- Currency and timezone.
- Item labels and supported attributes.
- Operating hours and availability schedules.
- Tax/service-charge settings.
- Feature flags for AI, reviews, ordering and promotions.
- Language-ready strings rather than hardcoded text everywhere.

Theme customization must use validated design tokens. Do not allow arbitrary admin CSS or unsafe HTML injection.

---

# 10. DEMO DATA REQUIREMENTS

Seed realistic, clearly labelled sample data for at least three distinct venue types:
1. A café/bakery.
2. A multi-cuisine restaurant.
3. A bar or casual dining venue (food and non-alcoholic items can be used for the demo).

Include:
- Different category structures and menu sizes.
- Sample dish images with appropriate source/provenance.
- Item prices in a consistent demo currency per restaurant.
- Verified-vs-unknown attribute examples.
- Scheduled items, sold-out items, date exceptions and different service windows.
- At least two tables per demo restaurant.
- Sample order tickets showing original orders and add-on orders.
- Demo kitchen statuses.
- Mock payment and notification events.
- Clearly labelled demo analytics.

Do not use fabricated real customer reviews, false popularity labels, or invented real-world restaurant affiliations. Demo content must be identifiable as sample content.

---

# 11. NON-FUNCTIONAL AND SECURITY REQUIREMENTS

- Enforce tenant-level access in backend services.
- Validate all input with typed schemas.
- Validate upload signatures, size, page count and processing limits.
- Keep secrets in environment variables/secret management.
- Do not commit `.env` files, credentials or real customer data.
- Use secure session/authentication practices and CSRF protection where applicable.
- Rate-limit public chat, recommendation, upload and order endpoints.
- Verify payment webhook signatures and deduplicate events.
- Use transactions for order creation, bill locking and payment state changes.
- Use idempotency keys for repeated client requests and provider callbacks.
- Calculate all prices/taxes on the backend.
- Never treat an unverified redirect as payment success.
- Keep audit logs for sensitive admin and order state changes.
- Avoid leaking phone/email addresses in logs or public receipt URLs.
- Use secure, unguessable receipt and table-session access tokens.
- Make notification failures retryable without repeating payment or order creation.
- Document retention and privacy decisions for contact details.
- Include database backups/migration instructions for cloud deployment.
- Provide graceful fallback if AI, OCR, SMS, email, payment or POS providers are unavailable.

---

# 12. TEST STRATEGY AND ACCEPTANCE SCENARIOS

Tests must be written alongside each module, not postponed until the end.

## Core end-to-end scenarios

### Scenario A — QR menu
- Open a table QR.
- Resolve correct restaurant and table.
- Browse categories and dish details.
- Verify unavailable dishes cannot be ordered.

### Scenario B — PDF/image ingestion
- Upload a selectable PDF.
- Upload a scanned image.
- Verify extracted candidates and confidence/source data.
- Correct an item and price.
- Approve and publish.
- Verify a failed ingestion does not replace the existing live menu.

### Scenario C — availability
- Configure an item for lunch hours.
- Test immediately before, during and after the availability window.
- Test a date exception and manual sold-out override.
- Verify backend order validation matches the displayed state.

### Scenario D — recommendation
- Request vegetarian food under a budget.
- Verify only eligible current menu items are returned.
- Apply admin promotion/demotion and verify ranking changes.
- Verify boosts cannot override availability or hard dietary constraints.
- Ask about an unknown allergen/ingredient and verify the system does not guess.

### Scenario E — original order plus add-on
- Open Table 12 session.
- Submit two items as Order A.
- Verify kitchen ticket includes Table 12 and the correct items.
- While Order A is preparing, add a dessert.
- Verify a distinct Add-on Order B appears for Table 12.
- Verify Order A remains unchanged.
- Verify both valid tickets contribute to the running bill exactly once.

### Scenario F — payment
- Request bill.
- Verify server-calculated total.
- Start mock checkout.
- Simulate failure and verify session recovery.
- Retry successfully.
- Replay the same payment event and verify no duplicate payment/receipt.
- Verify only a verified successful payment marks the bill paid.

### Scenario G — receipt notifications
- Verify receipt is generated once.
- Verify mock SMS/email jobs are recorded as simulated, not falsely marked as externally sent.
- Simulate a provider failure and retry.
- Verify notification retry does not duplicate the order or payment.

### Scenario H — tenant isolation
- Create two restaurants with separate owners.
- Attempt to access another tenant’s menu administration, orders, tables, receipts and integration settings.
- Verify unauthorized requests fail.
- Verify public QR/session tokens cannot be used to access unrelated sessions.

### Scenario I — kitchen operations
- Submit an order.
- Verify kitchen staff can change only permitted order states.
- Verify unauthorized status transitions are rejected and audited.
- Verify add-on tickets are visually distinct and time-ordered.

---

# 13. IMPLEMENTATION ORDER

Build a working vertical slice first, then expand the system. Do not generate the full product in a single giant coding task.

## Phase 0 — Inspect and plan
- Inspect repository, toolchain and installed dependencies.
- Create `docs/MASTER_BUILD_SPEC.md` from this file if it does not already exist.
- Create `docs/IMPLEMENTATION_CHECKLIST.md`, `docs/ARCHITECTURE.md`, `docs/API_SPEC.md` and `docs/DECISIONS.md`.
- Identify unresolved provider choices without blocking local mock implementations.
- Report the plan before making large changes.

## Phase 1 — Foundation
- Frontend and backend scaffolding.
- PostgreSQL and migrations.
- Health endpoints and seed data.
- Shared design tokens and reusable UI primitives.
- Test/lint commands and local startup instructions.

## Phase 2 — Customer menu
- Restaurant public pages.
- Categories, item cards, details, search and filters.
- Table QR resolution and demo table context.
- Responsive premium UI.

## Phase 3 — Admin menu management
- Authentication and restaurant memberships.
- Owner dashboard.
- Create/edit categories and items.
- Price, photo, availability and publishing controls.
- QR management.

## Phase 4 — Availability and ranking controls
- Schedule engine.
- Weekly and date-specific availability.
- Sold-out overrides and timezone tests.
- Admin recommendation boost/demotion.
- Shared server-side eligibility service.

## Phase 5 — AI discovery
- Structured dish attributes.
- Recommendation filtering/ranking.
- Ask-a-dish chat.
- Randomizer.
- Grounding, output validation, timeouts and evaluation tests.

## Phase 6 — PDF/image ingestion
- Upload/storage.
- PDF parsing and OCR.
- Structured extraction.
- Candidate review/editing.
- Approval and safe publishing.

## Phase 7 — Table sessions and kitchen
- Table sessions and secure tokens.
- Order creation and server-side totals.
- Kitchen display and order state machine.
- Distinct add-on tickets linked to an open session.
- Running bill and concurrency/idempotency tests.

## Phase 8 — Checkout and receipt
- Bill snapshots and payment-pending flow.
- Mock payment provider.
- Verified payment event simulation.
- Secure receipt generation.
- Mock SMS/email providers and retry queue.

## Phase 9 — POS and real-provider readiness
- Mock POS adapter.
- Integration status and retry workflows.
- Provider selection and official sandbox setup after credentials are available.
- Payment/webhook security review.
- Do not claim live integration until tested with the provider.

## Phase 10 — Hardening and deployment
- Full test suite and end-to-end tests.
- Security/tenant isolation checks.
- Error handling and observability.
- Backup/migration documentation.
- Select Railway or GCP based on runtime, worker, storage, database, secrets and cost requirements.
- Deploy only after local acceptance criteria are met.

After each phase, update the checklist with status and evidence. Do not mark a module complete simply because files were generated.

---

# 14. DEFINITION OF DONE

The prototype is ready for a controlled demo when:

- [ ] QR codes open the correct restaurant/table menu.
- [ ] Restaurant owners can manage prices and availability without code changes.
- [ ] Weekly schedules, date exceptions and sold-out overrides are respected.
- [ ] Admins can promote/demote recommendations without bypassing hard constraints.
- [ ] PDF/image menus can be extracted, reviewed and published.
- [ ] AI recommendations and Q&A are grounded in current menu data.
- [ ] Customers can submit an order associated with a table.
- [ ] Kitchen staff can see and progress orders.
- [ ] Customers can add items after the initial kitchen submission.
- [ ] Add-on tickets remain separate and appear on the same session’s bill.
- [ ] Bill totals are calculated server-side and are consistent.
- [ ] Mock checkout handles success/failure and duplicate events safely.
- [ ] Receipt generation and mock SMS/email jobs work with accurate status.
- [ ] Tenant isolation, upload validation and authorization tests pass.
- [ ] Local setup is reproducible from documented instructions.
- [ ] Known limitations and unimplemented live integrations are documented.

---


## Documentation, Project Memory and Folder-Structure Rules

These rules are mandatory for Claude Code on every implementation phase and every meaningful change.

- Maintain a clear, human-readable project knowledge base: `docs/PROJECT_CONTEXT.md` (current system overview and how the pieces connect), `docs/PROJECT_MEMORY.md` (durable decisions, conventions, important discoveries and lessons), `docs/CHANGELOG.md` (dated changes), `docs/DECISIONS.md` (architecture/product decisions and rationale), and `docs/IMPLEMENTATION_CHECKLIST.md` (module status, acceptance evidence and next steps).
- Keep the root `README.md` accurate as the entry point: what the product does, architecture summary, prerequisites, setup, environment variables, migrations, seed data, tests, run commands, troubleshooting and links to the docs.
- Before making changes, read the relevant project context, memory, decisions, checklist and module documentation. Do not assume the repository state from a previous chat or session.
- After every meaningful code/configuration/schema/API/UI change, update the relevant documentation in the same task. Do not defer documentation updates to a later phase.
- Update project context whenever architecture, module boundaries, data flow, setup, environment configuration or runtime behavior changes. Update project memory when a durable lesson, convention or constraint is discovered. Record consequential choices and alternatives in decisions. Add a dated changelog entry for meaningful user-visible or architectural changes.
- Keep documentation factual and useful to the next developer. Include purpose, current behavior, key files, data flow, dependencies, commands, assumptions, limitations, test evidence and known issues. Clearly distinguish implemented, partially implemented, mocked and planned functionality.
- Do not create competing or redundant “context”, “memory”, or documentation files with overlapping purposes. Use the canonical paths above unless the existing repository already has an established equivalent; if so, preserve it and document the mapping.
- Organize folders by clear responsibility and domain, using consistent names and a predictable hierarchy. Avoid dumping unrelated files into root, oversized catch-all modules, vague names such as `misc`, or duplicate implementations. Keep a short architecture/folder guide in `docs/ARCHITECTURE.md`.
- Keep documentation synchronized with the code asynchronously in the practical sense: update it as part of each change/phase, not only at the end. Do not run background or untracked documentation jobs; the final state of every completed task must have matching code, tests, checklist and docs.
- If the user introduces a new requirement, first record it in the relevant specification/decision log, identify affected modules and tests, update the checklist, implement it in a scoped phase, and then update context/memory/changelog and the relevant module docs.
- Before finishing a task, verify that the folder structure is still intuitive, documentation links and commands are accurate, and no documentation claims a feature or test exists when it does not.


# 15. CLOU​​D CODE MASTER INSTRUCTION

**Copy the instruction below into Cloud Code after saving this document in the repository.**

You are the lead full-stack engineer building this product. Treat `docs/MASTER_BUILD_SPEC.md` as the source of truth.

## Your first task

1. Inspect the repository, current files, runtime versions and dependencies.
2. Read the complete master specification.
3. If the repository already contains work, preserve it and identify what can be reused.
4. Create/update:
   - `docs/IMPLEMENTATION_CHECKLIST.md`
   - `docs/ARCHITECTURE.md`
   - `docs/API_SPEC.md`
   - `docs/DECISIONS.md`
5. Record unresolved decisions, including the eventual payment, SMS, email, POS and hosting providers. Use mock adapters so local work can proceed.
6. Present a concise implementation plan for **Phase 1 only**.
7. Implement Phase 1 after the plan is clear: frontend/backend scaffolding, database setup and migrations, health endpoints, seed-data infrastructure, shared UI foundation, automated tests and local startup instructions.
8. Run the checks that are available. Report actual outcomes and blockers.

## Non-negotiable engineering rules

- Do not generate the entire application in one pass.
- Do not skip modules or acceptance criteria from the checklist.
- Do not mark work complete without running the relevant tests.
- Do not create fake “live” payment, SMS, email, POS or AI integrations.
- Do not hardcode restaurant prices, availability, schedule rules or recommendation boosts in source code.
- Use admin-managed database records for operational configuration.
- Implement server-side authorization, tenant isolation, exact money calculations and transactional order workflows.
- Keep order tickets, table sessions, bills, payments, receipts and notification delivery as separate but linked concepts.
- Additional items must create distinct kitchen tickets linked to the open session.
- Do not allow an admin ranking boost to override hard availability or dietary constraints.
- Preserve historical order-item price/name snapshots.
- Validate uploaded files and AI output.
- Protect secrets and private customer information.
- Use a polished, accessible and responsive design system. Prefer compatible, well-maintained libraries over unnecessary dependencies.
- Keep components reusable and restaurant branding configurable.
- Add tests for business rules and error paths, not just happy paths.
- Review diffs and avoid destructive changes without a clear reason.
- If a specification detail is ambiguous, document the decision and select the safest reasonable default; ask only when a missing decision truly blocks implementation.
- Never claim tests, deployments or integrations succeeded unless they actually did.

## After every phase and every meaningful change

1. Update `docs/IMPLEMENTATION_CHECKLIST.md` with status and acceptance evidence.
2. Update `docs/PROJECT_CONTEXT.md` if the architecture, workflows, folder structure, setup or runtime behavior changed.
3. Update `docs/PROJECT_MEMORY.md` with durable conventions, constraints and discoveries; do not use it as a duplicate changelog.
4. Record consequential choices and rationale in `docs/DECISIONS.md`.
5. Add a dated entry to `docs/CHANGELOG.md` for meaningful changes.
6. Update `README.md`, `docs/ARCHITECTURE.md`, `docs/API_SPEC.md` and relevant module documentation whenever their information changes.
7. List files created or modified.
8. Summarize working functionality.
9. Report tests run and their actual results.
10. Document known issues, security considerations and incomplete integrations.
11. Recommend the next phase.
12. Stop at the phase boundary rather than starting every remaining phase automatically.

Documentation must be updated in the same task as the change. Before finishing, verify that folder structure, documentation links, commands and feature-status claims match the actual repository.

## Start now

Inspect the repository and begin **Phase 0 followed by Phase 1 only**. The first deliverable is a reproducible local application foundation, not a collection of disconnected mockup screens.
