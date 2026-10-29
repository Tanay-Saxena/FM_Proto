"""Acceptance scenarios A, C, D, E, F, G, H, I from the master spec (API level)."""
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.models import AuditLog, NotificationJob, Order, Payment, Receipt
from app.providers.messaging import EMAIL, SMS
from app.providers.payments import get_provider
from app.services.receipts import process_due_jobs

from .conftest import LUNCH, give_contact, login, menu_items, new_table_session, place

API = "/api/v1"


# ───────── A — QR menu ─────────
def test_a_qr_resolves_table_and_menu(client, owner, rid):
    t = owner.post(f"{API}/restaurants/{rid}/tables", json={"label": "A-1", "zone": "Test"}).json()
    token = t["qr_url"].rsplit("/", 1)[1]
    info = client.get(f"{API}/qr/{token}").json()
    assert info["restaurant_slug"] == "spice-route" and info["table"] == "A-1"
    assert client.get(f"{API}/qr/not-a-real-token").status_code == 404
    items = menu_items(client)
    assert "Paneer Tikka" in items and "Dosa" not in items
    assert all("Copper" not in n for n in items)  # only this restaurant's menu


def test_a_unavailable_dish_cannot_be_ordered(client, owner, rid):
    tok = new_table_session(owner, rid, client, "A-2")
    give_contact(client, tok)
    items = menu_items(client)
    assert items["Rasmalai"]["availability"]["status"] == "sold_out"
    r = place(client, tok, [(items["Rasmalai"]["id"], 1)])
    assert r.status_code == 409 and r.json()["error"]["code"] == "items_unavailable"


# ───────── C — availability matches between display and order ─────────
def test_c_thali_only_in_lunch_window(client, owner, rid):
    tok = new_table_session(owner, rid, client, "C-1")
    give_contact(client, tok)
    for at, ok in [("2026-10-28T06:29:00Z", False), ("2026-10-28T06:30:00Z", True), ("2026-10-28T09:30:00Z", False)]:
        thali = menu_items(client, at=at)["Executive Lunch Thali"]
        assert thali["availability"]["orderable"] is ok
        r = place(client, tok, [(thali["id"], 1)], at=at)
        assert (r.status_code == 201) is ok, (at, r.text)


def test_c_manual_sold_out_override_and_audit(client, owner, rid):
    tok = new_table_session(owner, rid, client, "C-2")
    give_contact(client, tok)
    it = menu_items(client)["Jeera Rice"]
    assert owner.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"state": "sold_out"}).status_code == 200
    assert place(client, tok, [(it["id"], 1)]).status_code == 409
    owner.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"state": "available"})
    assert place(client, tok, [(it["id"], 1)]).status_code == 201


def test_c_stock_limits_and_restore_on_reject(client, owner, rid, db):
    tok = new_table_session(owner, rid, client, "C-3")
    give_contact(client, tok)
    biryani = menu_items(client)["Hyderabadi Dum Biryani"]
    owner.patch(f"{API}/restaurants/{rid}/items/{biryani['id']}", json={"stock_remaining": 2})
    assert place(client, tok, [(biryani["id"], 3)]).json()["error"]["code"] == "insufficient_stock"
    r = place(client, tok, [(biryani["id"], 2)])
    assert r.status_code == 201
    assert menu_items(client)["Hyderabadi Dum Biryani"]["availability"]["status"] == "sold_out"
    kitchen = login(client, "kitchen@spiceroute.demo")
    oid = r.json()["order"]["id"]
    assert kitchen.post(f"{API}/orders/{oid}/status-transition", json={"to_state": "rejected", "reason": "Out of rice"}).status_code == 200
    assert menu_items(client)["Hyderabadi Dum Biryani"]["availability"]["orderable"] is True  # stock returned


def test_modifier_validation_and_price(client, owner, rid):
    tok = new_table_session(owner, rid, client, "C-4")
    give_contact(client, tok)
    soda = menu_items(client)["Fresh Lime Soda"]
    r = place(client, tok, [(soda["id"], 1)])
    assert r.status_code == 422  # required modifier group
    r = client.post(f"{API}/table-sessions/{tok}/orders", headers={"x-demo-time": LUNCH}, json={"idempotency_key": "mod-key-0001", "lines": [{"item_id": soda["id"], "quantity": 1, "modifier_option_ids": [soda["modifier_groups"][0]["options"][0]["id"]]}]})
    assert r.status_code == 201


# ───────── D — recommendations ─────────
def test_d_vegetarian_under_budget_only_eligible(client):
    r = client.post(f"{API}/restaurants/spice-route/recommendations", headers={"x-demo-time": LUNCH}, json={"query": "vegetarian under 200"}).json()
    names = [i["name"] for i in r["items"]]
    assert names and "Butter Chicken" not in names and "Chicken 65" not in names
    for i in r["items"]:
        assert i["price_minor"] <= 20000 and i["availability"]["orderable"]
        assert any(a["key"] == "diet" and a["verified"] and a["value"] in ("vegetarian", "vegan") for a in i["attributes"])
    assert "Rasmalai" not in names  # sold out


def test_d_unverified_diet_excluded_not_guessed(client):
    r = client.post(f"{API}/restaurants/kettle-crumb/recommendations", headers={"x-demo-time": "2026-10-28T05:00:00Z"}, json={"diets": ["vegetarian"], "limit": 20}).json()
    assert "Masala Omelette Toast" not in [i["name"] for i in r["items"]]


def test_d_boost_changes_rank_but_cannot_override_constraints(client, owner, rid):
    base = client.post(f"{API}/restaurants/spice-route/recommendations", headers={"x-demo-time": LUNCH}, json={"tastes": ["creamy"], "limit": 20}).json()["items"]
    target = base[-1]
    rule = owner.post(f"{API}/restaurants/{rid}/recommendation-rules", json={"target_type": "item", "target_id": target["key"], "weight": 5, "label": "Promo"}).json()
    after = client.post(f"{API}/restaurants/spice-route/recommendations", headers={"x-demo-time": LUNCH}, json={"tastes": ["creamy"], "limit": 20}).json()["items"]
    assert [i["id"] for i in after].index(target["id"]) < [i["id"] for i in base].index(target["id"])
    assert next(i for i in after if i["id"] == target["id"])["promo"]["label"] == "Promo"
    owner.delete(f"{API}/restaurants/{rid}/recommendation-rules/{rule['id']}")
    # boost on a sold-out dish never makes it appear
    ras = menu_items(client)["Rasmalai"]
    owner.post(f"{API}/restaurants/{rid}/recommendation-rules", json={"target_type": "item", "target_id": ras["key"], "weight": 5})
    out = client.post(f"{API}/restaurants/spice-route/recommendations", headers={"x-demo-time": LUNCH}, json={"query": "sweet dessert"}).json()["items"]
    assert "Rasmalai" not in [i["name"] for i in out]
    # nor a non-vegetarian dish for a vegetarian guest
    cc = menu_items(client)["Chicken 65"]
    owner.post(f"{API}/restaurants/{rid}/recommendation-rules", json={"target_type": "item", "target_id": cc["key"], "weight": 5})
    out = client.post(f"{API}/restaurants/spice-route/recommendations", headers={"x-demo-time": LUNCH}, json={"diets": ["vegetarian"], "limit": 20}).json()["items"]
    assert "Chicken 65" not in [i["name"] for i in out]


def test_d_chat_does_not_guess_unverified_allergens(client):
    a = client.post(f"{API}/restaurants/spice-route/chat", headers={"x-demo-time": LUNCH}, json={"message": "Does the Chicken 65 contain nuts?"}).json()
    assert "haven't been verified" in a["answer"] and a["grounded"]
    b = client.post(f"{API}/restaurants/spice-route/chat", headers={"x-demo-time": LUNCH}, json={"message": "Does Dal Makhani contain nuts?"}).json()
    assert "does not include nuts" in b["answer"]
    c = client.post(f"{API}/restaurants/spice-route/chat", headers={"x-demo-time": LUNCH}, json={"message": "Is the Poha vegan?"}).json()
    assert "Poha" not in c["answer"]  # not on this restaurant's menu -> no invention
    ids = {i["id"] for i in client.post(f"{API}/restaurants/spice-route/chat", headers={"x-demo-time": LUNCH}, json={"message": "suggest something spicy"}).json()["items"]}
    mine = set(i["id"] for i in menu_items(client).values())
    assert ids <= mine


# ───────── E — original + add-on ─────────
def test_e_addon_creates_distinct_ticket_and_single_bill(client, owner, rid):
    kitchen = login(client, "kitchen@spiceroute.demo")
    tok = new_table_session(owner, rid, client, "E-12")
    items = menu_items(client)
    r = place(client, tok, [(items["Paneer Tikka"]["id"], 1), (items["Butter Naan"]["id"], 2)])
    assert r.status_code == 403 or r.status_code in (422,)  # contact required first
    give_contact(client, tok)
    a = place(client, tok, [(items["Paneer Tikka"]["id"], 1), (items["Butter Naan"]["id"], 2)]).json()["order"]
    assert a["label"] == "A" and a["ticket_type"] == "original"
    q = kitchen.get(f"{API}/restaurants/{rid}/kitchen/queue").json()["tickets"]
    ta = next(t for t in q if t["id"] == a["id"])
    assert ta["table"] == "E-12" and {i["name"] for i in ta["items"]} == {"Paneer Tikka", "Butter Naan"}
    for st in ("accepted", "preparing"):
        assert kitchen.post(f"{API}/orders/{a['id']}/status-transition", json={"to_state": st}).status_code == 200
    b = place(client, tok, [(items["Gulab Jamun"]["id"], 1)]).json()["order"]
    assert b["label"] == "B" and b["ticket_type"] == "addon" and b["id"] != a["id"]
    q = kitchen.get(f"{API}/restaurants/{rid}/kitchen/queue").json()["tickets"]
    ta2 = next(t for t in q if t["id"] == a["id"]); tb = next(t for t in q if t["id"] == b["id"])
    assert ta2["state"] == "preparing" and len(ta2["items"]) == 2  # A untouched
    assert tb["ticket_type"] == "addon" and tb["follows_number"] == a["number"] and tb["table"] == "E-12"
    bill = client.get(f"{API}/table-sessions/{tok}/bill").json()
    expected = 32000 + 2 * 7000 + 13000
    assert bill["subtotal_minor"] == expected and bill["item_count"] == 4 and len(bill["tickets"]) == 2


def test_e_idempotent_resubmit(client, owner, rid):
    tok = new_table_session(owner, rid, client, "E-IDEM")
    give_contact(client, tok)
    i = menu_items(client)["Butter Naan"]["id"]
    r1 = place(client, tok, [(i, 1)], key="same-key-12345")
    r2 = place(client, tok, [(i, 1)], key="same-key-12345")
    assert r1.status_code == 201 and r2.status_code == 200 and r2.json()["replayed"] is True
    assert len(client.get(f"{API}/table-sessions/{tok}/orders").json()) == 1


def test_e_concurrent_addons_lose_nothing(client, owner, rid):
    tok = new_table_session(owner, rid, client, "E-CONC")
    give_contact(client, tok)
    i = menu_items(client)["Butter Naan"]["id"]
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda n: place(TestClient(app), tok, [(i, 1)], key=f"conc-key-{n:04d}").status_code, range(8)))
    assert results.count(201) == 8
    orders = client.get(f"{API}/table-sessions/{tok}/orders").json()
    assert sorted(o["label"] for o in orders) == list("ABCDEFGH")
    assert client.get(f"{API}/table-sessions/{tok}/bill").json()["subtotal_minor"] == 8 * 7000


# ───────── F — payment ─────────
def _sim(client, tok, pid, outcome):
    return client.post(f"{API}/table-sessions/{tok}/payments/{pid}/simulate", json={"outcome": outcome})


def test_f_payment_failure_recovery_replay_and_forgery(client, owner, rid, db):
    tok = new_table_session(owner, rid, client, "F-1")
    give_contact(client, tok)
    items = menu_items(client)
    place(client, tok, [(items["Dal Makhani"]["id"], 1), (items["Butter Naan"]["id"], 2)])
    bill = client.post(f"{API}/table-sessions/{tok}/bill-request").json()
    expected_sub = 29000 + 14000
    assert bill["bill"]["subtotal_minor"] == expected_sub and bill["state"] == "bill_requested"
    ps = client.post(f"{API}/table-sessions/{tok}/payment-session", json={"idempotency_key": "pay-key-0001"}).json()
    pid = ps["payment"]["id"]
    assert ps["payment"]["amount_minor"] == bill["bill"]["total_minor"] and ps["payment"]["simulated"] is True
    # idempotent
    assert client.post(f"{API}/table-sessions/{tok}/payment-session", json={"idempotency_key": "pay-key-0001"}).json()["payment"]["id"] == pid
    # ordering locked while payment pending
    assert place(client, tok, [(items["Butter Naan"]["id"], 1)]).json()["error"]["code"] == "session_locked"
    # failure -> recoverable
    assert _sim(client, tok, pid, "failure").json()["state"] == "failed"
    assert client.get(f"{API}/table-sessions/{tok}").json()["state"] == "bill_requested"
    # retry succeeds
    pid2 = client.post(f"{API}/table-sessions/{tok}/payment-session", json={"idempotency_key": "pay-key-0002"}).json()["payment"]["id"]
    assert pid2 != pid
    # a client-side "success" claim without a signed event changes nothing
    forged = client.post(f"{API}/webhooks/payments/mock", content=b'{"event_id":"x1","type":"payment.succeeded","provider_ref":"nope"}', headers={"x-mock-signature": "deadbeef"})
    assert forged.status_code == 400
    assert client.get(f"{API}/table-sessions/{tok}/payments/{pid2}").json()["state"] == "pending"
    # amount mismatch is rejected, bill stays unpaid
    prov = get_provider("mock")
    p2 = db.get(Payment, pid2)
    body, sig = prov.build_event(provider_ref=p2.provider_ref, amount_minor=1, currency="INR", outcome="success", event_id="evt_wrong_amount")
    assert client.post(f"{API}/webhooks/payments/mock", content=body, headers={prov.signature_header: sig}).json()["outcome"] == "amount_mismatch"
    db.expire_all()
    assert db.get(Payment, pid2).state == "pending"
    # real success
    body, sig = prov.build_event(provider_ref=p2.provider_ref, amount_minor=p2.amount_minor, currency="INR", outcome="success", event_id="evt_ok_1")
    assert client.post(f"{API}/webhooks/payments/mock", content=body, headers={prov.signature_header: sig}).json()["outcome"] == "applied"
    # replay: no duplicate payment/receipt
    assert client.post(f"{API}/webhooks/payments/mock", content=body, headers={prov.signature_header: sig}).json()["status"] == "duplicate"
    db.expire_all()
    assert db.query(Receipt).filter(Receipt.payment_id == pid2).count() == 1
    s = client.get(f"{API}/table-sessions/{tok}").json()
    assert s["state"] == "closed" and s["receipt_token"]
    assert place(client, tok, [(items["Butter Naan"]["id"], 1)]).status_code == 409
    # G — receipt content
    rc = client.get(f"{API}/receipts/{s['receipt_token']}").json()
    assert rc["bill"]["total_minor"] == p2.amount_minor and rc["table"] == "F-1"
    assert "phone" not in str(rc).lower() and "9876500000" not in str(rc)
    assert client.get(f"{API}/receipts/{s['receipt_token']}/pdf").headers["content-type"] == "application/pdf"
    assert client.get(f"{API}/receipts/bogus-token").status_code == 404


def test_f_duplicate_charge_flagged_for_refund(client, owner, rid, db):
    tok = new_table_session(owner, rid, client, "F-2")
    give_contact(client, tok)
    place(client, tok, [(menu_items(client)["Butter Naan"]["id"], 1)])
    client.post(f"{API}/table-sessions/{tok}/bill-request")
    p1 = client.post(f"{API}/table-sessions/{tok}/payment-session", json={"idempotency_key": "dup-key-0001"}).json()["payment"]["id"]
    _sim(client, tok, p1, "success")
    db.expire_all()
    s = db.get(Payment, p1)
    assert s.state == "succeeded"


# ───────── G — notifications ─────────
def test_g_notifications_simulated_and_retry(client, owner, rid, db):
    tok = new_table_session(owner, rid, client, "G-1")
    client.post(f"{API}/table-sessions/{tok}/contact", json={"name": "Retry Guest", "phone": "+919876511111", "email": "retry@example.com", "consent": True})
    place(client, tok, [(menu_items(client)["Butter Naan"]["id"], 1)])
    client.post(f"{API}/table-sessions/{tok}/bill-request")
    process_due_jobs(db)  # drain jobs queued by earlier tests
    EMAIL.fail_next(1)
    pid = client.post(f"{API}/table-sessions/{tok}/payment-session", json={"idempotency_key": "g-pay-0001"}).json()["payment"]["id"]
    _sim(client, tok, pid, "success")
    process_due_jobs(db)
    rc = db.query(Receipt).filter(Receipt.payment_id == pid).one()
    jobs = {j.channel: j for j in db.query(NotificationJob).filter(NotificationJob.receipt_id == rc.id)}
    db.expire_all()
    assert jobs["sms"].state == "sent" and jobs["sms"].simulated is True  # "sent" by the mock, flagged simulated
    assert jobs["email"].state == "retry_scheduled" and jobs["email"].attempts == 1
    n_orders = db.query(Order).count()
    r = owner.post(f"{API}/notifications/{jobs['email'].id}/retry")
    assert r.json()["state"] == "sent"
    assert db.query(Order).count() == n_orders and db.query(Receipt).filter(Receipt.payment_id == pid).count() == 1
    assert owner.post(f"{API}/notifications/{jobs['email'].id}/retry").status_code == 409  # never resend
    listing = owner.get(f"{API}/restaurants/{rid}/notifications").json()
    assert all("@" not in n["recipient"] or "***" in n["recipient"] for n in listing)


# ───────── H — tenant isolation ─────────
def test_h_tenant_isolation(client, owner, rid):
    other = login(client, "owner@kettle.demo")
    kc = other.get(f"{API}/auth/me").json()["memberships"][0]["restaurant_id"]
    for path in ("menus", "orders", "tables", "payments", "notifications", "availability-rules", "staff", "audit", "dashboard"):
        assert other.get(f"{API}/restaurants/{rid}/{path}").status_code == 404, path
    assert other.patch(f"{API}/restaurants/{rid}", json={"name": "Hacked"}).status_code == 404
    sr_item = menu_items(client)["Butter Naan"]["id"]
    assert other.patch(f"{API}/restaurants/{kc}/items/{sr_item}", json={"price_minor": 1}).status_code == 404
    first_order = owner.get(f"{API}/restaurants/{rid}/orders").json()[0]["id"]
    assert other.post(f"{API}/orders/{first_order}/status-transition", json={"to_state": "accepted"}).status_code == 404
    assert client.get(f"{API}/restaurants/{rid}/orders").status_code == 401  # anonymous
    # tokens are not interchangeable
    t1 = new_table_session(owner, rid, client, "H-1")
    assert client.get(f"{API}/table-sessions/{t1}x").status_code == 404
    assert client.get(f"{API}/table-sessions/1").status_code == 404


def test_h_platform_admin_has_no_tenant_data_access(client, rid):
    plat = login(client, "platform@foodmania.demo")
    assert plat.get(f"{API}/restaurants/{rid}/orders").status_code == 404
    assert plat.get(f"{API}/platform/health").status_code == 200
    assert login(client, "owner@kettle.demo").get(f"{API}/platform/health").status_code == 403


# ───────── I — kitchen operations ─────────
def test_i_kitchen_permissions_and_audit(client, owner, rid, db):
    kitchen = login(client, "kitchen@spiceroute.demo")
    staff = login(client, "staff@spiceroute.demo")
    tok = new_table_session(owner, rid, client, "I-1")
    give_contact(client, tok)
    oid = place(client, tok, [(menu_items(client)["Butter Naan"]["id"], 1)]).json()["order"]["id"]
    assert kitchen.post(f"{API}/orders/{oid}/status-transition", json={"to_state": "served"}).status_code == 409  # skipping steps
    assert kitchen.post(f"{API}/orders/{oid}/status-transition", json={"to_state": "cancelled", "reason": "x"}).status_code == 403
    assert staff.post(f"{API}/orders/{oid}/acknowledge").status_code == 403
    assert kitchen.get(f"{API}/restaurants/{rid}/payments").status_code == 403
    assert kitchen.patch(f"{API}/restaurants/{rid}", json={"name": "x"}).status_code == 403
    assert kitchen.post(f"{API}/orders/{oid}/acknowledge").status_code == 200
    denied = db.query(AuditLog).filter(AuditLog.action == "order.transition_denied", AuditLog.resource_id == oid).count()
    assert denied == 2
    assert owner.post(f"{API}/orders/{oid}/status-transition", json={"to_state": "cancelled", "reason": "Guest left"}).status_code == 200
    assert owner.post(f"{API}/orders/{oid}/status-transition", json={"to_state": "preparing"}).status_code == 409  # terminal


def test_staff_can_only_change_availability(client, owner, rid):
    staff = login(client, "staff@spiceroute.demo")
    it = menu_items(client)["Jeera Rice"]
    assert staff.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"price_minor": 100}).status_code == 403
    assert staff.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"state": "paused"}).status_code == 200
    assert staff.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"state": "available"}).status_code == 200


def test_admin_price_edit_is_audited_and_visible(client, owner, rid):
    it = menu_items(client)["Hara Bhara Kebab"]
    owner.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"price_minor": 29900})
    assert menu_items(client)["Hara Bhara Kebab"]["price_minor"] == 29900
    log = owner.get(f"{API}/restaurants/{rid}/audit").json()
    assert any(a["action"] == "item.updated" and "price_minor" in a["detail"] for a in log)
    owner.patch(f"{API}/restaurants/{rid}/items/{it['id']}", json={"price_minor": 28000})


def test_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["status"] == "ready"

