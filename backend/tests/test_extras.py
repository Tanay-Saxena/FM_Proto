"""Prototype-completion features: refunds, reviews, photo upload, reorder, reopen/transfer, origin check, retention."""
import io
from datetime import datetime, timedelta, timezone

from PIL import Image

from app.models import Payment, TableSession
from app.providers.payments import get_provider
from app.retention import purge_contacts

from .conftest import LUNCH, give_contact, login, menu_items, new_table_session, place

API = "/api/v1"


def _pay(client, owner, rid, db, label, evt):
    tok = new_table_session(owner, rid, client, label)
    give_contact(client, tok)
    items = menu_items(client)
    place(client, tok, [(items["Butter Naan"]["id"], 1)])
    client.post(f"{API}/table-sessions/{tok}/bill-request")
    pid = client.post(f"{API}/table-sessions/{tok}/payment-session", json={"idempotency_key": f"k-{evt}-0001"}).json()["payment"]["id"]
    p = db.get(Payment, pid)
    prov = get_provider("mock")
    body, sig = prov.build_event(provider_ref=p.provider_ref, amount_minor=p.amount_minor, currency="INR", outcome="success", event_id=evt)
    assert client.post(f"{API}/webhooks/payments/mock", content=body, headers={prov.signature_header: sig}).json()["outcome"] == "applied"
    return tok, pid, client.get(f"{API}/table-sessions/{tok}").json()["receipt_token"]


def test_review_once_and_visible_to_owner(client, owner, rid, db):
    tok, pid, rt = _pay(client, owner, rid, db, "X-REV", "evt_rev_1")
    assert client.post(f"{API}/receipts/{rt}/review", json={"rating": 0}).status_code == 422
    assert client.post(f"{API}/receipts/{rt}/review", json={"rating": 5, "comment": "Great naan"}).status_code == 201
    assert client.post(f"{API}/receipts/{rt}/review", json={"rating": 1}).json()["error"]["code"] == "already_reviewed"
    assert client.get(f"{API}/receipts/{rt}").json()["review"]["rating"] == 5
    assert client.post(f"{API}/receipts/nope/review", json={"rating": 4}).status_code == 404
    rv = owner.get(f"{API}/restaurants/{rid}/reviews").json()
    assert rv["count"] >= 1 and any(r["comment"] == "Great naan" for r in rv["reviews"])
    assert client.get(f"{API}/restaurants/{rid}/reviews").status_code == 401  # guests can't read the review inbox


def test_refund_owner_only_audited_and_blocks_review(client, owner, rid, db):
    tok, pid, rt = _pay(client, owner, rid, db, "X-REF", "evt_ref_1")
    kitchen = login(client, "kitchen@spiceroute.demo")
    manager = login(client, "manager@spiceroute.demo")
    assert kitchen.post(f"{API}/restaurants/{rid}/payments/{pid}/refund", json={"reason": "x"}).status_code == 403
    assert manager.post(f"{API}/restaurants/{rid}/payments/{pid}/refund", json={"reason": "x"}).status_code == 403
    assert owner.post(f"{API}/restaurants/{rid}/payments/{pid}/refund", json={"reason": ""}).status_code == 422
    r = owner.post(f"{API}/restaurants/{rid}/payments/{pid}/refund", json={"reason": "Guest was charged for a dish not served"})
    assert r.status_code == 200 and r.json()["state"] == "refunded" and r.json()["simulated"] is True
    assert owner.post(f"{API}/restaurants/{rid}/payments/{pid}/refund", json={"reason": "again"}).json()["state"] == "refunded"  # idempotent
    rc = client.get(f"{API}/receipts/{rt}").json()
    assert rc["refund"]["amount_minor"] == r.json()["refunded_minor"]
    assert client.post(f"{API}/receipts/{rt}/review", json={"rating": 5}).json()["error"]["code"] == "refunded"
    audit = owner.get(f"{API}/restaurants/{rid}/audit").json()
    assert any(a["action"] == "payment.refunded" for a in (audit if isinstance(audit, list) else audit.get("entries", audit)))
    # a refunded payment no longer counts as revenue (the dashboard sums only "succeeded")
    db.expire_all()
    assert db.get(Payment, pid).state == "refunded"


def _png(color=(200, 80, 40), size=(64, 64), fmt="PNG"):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, fmt)
    return b.getvalue()


def test_dish_photo_upload_validated_and_served(client, owner, rid):
    items = menu_items(client)
    iid = items["Butter Naan"]["id"]
    url = f"{API}/restaurants/{rid}/items/{iid}/image"
    assert owner.post(url, files={"file": ("x.png", b"not an image", "image/png")}).status_code == 422
    assert owner.post(url, files={"file": ("x.gif", _png(fmt="GIF"), "image/gif")}).status_code == 422
    r = owner.post(url, files={"file": ("naan.png", _png(size=(2000, 1000)), "image/png")})
    assert r.status_code == 200, r.text
    img = r.json()["image"]
    assert img["kind"] == "photo" and img["url"].startswith("/api/v1/media/dishes/")
    served = client.get(img["url"])
    assert served.status_code == 200 and served.headers["content-type"] == "image/jpeg"
    got = Image.open(io.BytesIO(served.content))
    assert got.format == "JPEG" and max(got.size) <= 1200  # re-encoded and downscaled
    assert client.get(f"{API}/media/../../etc/passwd").status_code in (404, 422)
    assert client.get(f"{API}/media/dishes/other/missing.jpg").status_code == 404
    staff = login(client, "staff@spiceroute.demo")
    assert staff.post(url, files={"file": ("n.png", _png(), "image/png")}).status_code == 403
    assert owner.delete(url).json()["image"]["kind"] == "plate"


def test_reorder_and_category_delete(client, owner, rid):
    menus = owner.get(f"{API}/restaurants/{rid}/menus").json()
    draft = next((m for m in menus if m["status"] == "draft"), None)
    if not draft:
        pub = next(m for m in menus if m["status"] == "published")
        draft = owner.post(f"{API}/restaurants/{rid}/menus/{pub['id']}/clone").json()
    mid = draft["id"]
    full = owner.get(f"{API}/restaurants/{rid}/menus/{mid}").json()
    ids = [c["id"] for c in full["categories"]]
    rev = list(reversed(ids))
    assert owner.post(f"{API}/restaurants/{rid}/menus/{mid}/reorder", json={"kind": "categories", "ids": rev[:-1]}).status_code == 422  # must list all
    assert owner.post(f"{API}/restaurants/{rid}/menus/{mid}/reorder", json={"kind": "categories", "ids": rev}).status_code == 200
    again = owner.get(f"{API}/restaurants/{rid}/menus/{mid}").json()
    assert [c["id"] for c in again["categories"]] == rev
    # non-empty categories can't be deleted; an empty one can
    assert owner.delete(f"{API}/restaurants/{rid}/categories/{ids[0]}").status_code == 409
    new = owner.post(f"{API}/restaurants/{rid}/menus/{mid}/categories", json={"name": "Temp"}).json()["id"]
    assert owner.delete(f"{API}/restaurants/{rid}/categories/{new}").status_code == 204


def test_session_reopen_and_transfer(client, owner, rid, db):
    tok = new_table_session(owner, rid, client, "X-MOVE")
    sid = db.query(TableSession).filter(TableSession.public_token == tok).first().id
    dest = owner.post(f"{API}/restaurants/{rid}/tables", json={"label": "X-DEST"}).json()["id"]
    act = lambda **b: owner.post(f"{API}/restaurants/{rid}/sessions/{sid}/action", json=b)
    assert act(action="reopen").status_code == 409  # not closed
    assert act(action="transfer", to_table_id=dest).json()["state"] == "open"
    db.expire_all()
    assert db.get(TableSession, sid).table.label == "X-DEST"
    assert client.get(f"{API}/table-sessions/{tok}").json()["table"] == "X-DEST"
    assert act(action="transfer", to_table_id=dest).status_code == 422  # same table
    assert act(action="force_close", reason="walked out").status_code == 200
    assert act(action="reopen").json()["state"] == "open"
    # a paid session can never be re-opened
    ptok, pid, _ = _pay(client, owner, rid, db, "X-PAID", "evt_reopen_1")
    psid = db.query(TableSession).filter(TableSession.public_token == ptok).first().id
    assert owner.post(f"{API}/restaurants/{rid}/sessions/{psid}/action", json={"action": "reopen"}).json()["error"]["code"] == "already_paid"


def test_cross_origin_writes_are_refused():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)  # own cookie jar: must not log in the shared anonymous client
    r = client.post(f"{API}/auth/login", json={"email": "owner@spiceroute.demo", "password": "demo1234"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "bad_origin"
    ok = client.post(f"{API}/auth/login", json={"email": "owner@spiceroute.demo", "password": "demo1234"}, headers={"origin": "http://localhost:3000"})
    assert ok.status_code == 200


def test_contact_retention_purge(client, owner, rid, db):
    tok = new_table_session(owner, rid, client, "X-PURGE")
    give_contact(client, tok)
    s = db.query(TableSession).filter(TableSession.public_token == tok).first()
    s.state, s.closed_at = "closed", datetime.now(timezone.utc) - timedelta(days=400)
    db.commit()
    assert purge_contacts(db, days=180) >= 1
    db.expire_all()
    s = db.get(TableSession, s.id)
    assert s.contact_phone is None and s.contact_email is None and s.contact_name is None and s.contact_purged_at is not None
    assert purge_contacts(db, days=180) == 0  # idempotent
