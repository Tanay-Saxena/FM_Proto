"""Public/customer API. No account needed; table access is via unguessable session tokens."""
from __future__ import annotations

import hashlib
import io
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..defaults import merged_config, merged_theme
from ..deps import demo_now
from ..models import AnalyticsEvent, Bill, Item, Menu, Order, Payment, Receipt, Restaurant, Review, TableSession
from ..providers.payments import MockPaymentProvider, get_provider
from ..ratelimit import limit
from ..schemas import ReviewIn, AnalyticsIn, ChatIn, ContactIn, MockCheckoutIn, OrderIn, PaymentSessionIn, Preferences
from ..services import chat as chat_service
from ..services import orders as order_service
from ..services import recommend as rec
from ..services import sessions as sess
from ..services.availability import evaluate_item
from ..services.audit import audit
from ..services.billing import compute_bill
from ..services.errors import DomainError
from ..services.menu import build_public_menu, public_restaurant, published_menu, rules_index, serialize_item
from ..services.receipts import mask

router = APIRouter()


def restaurant_by_ref(db: Session, ref: str) -> Restaurant:
    r = db.query(Restaurant).filter((Restaurant.slug == ref) | (Restaurant.id == ref)).first()
    if not r or r.status != "active":
        raise DomainError("not_found", "Restaurant not found.", 404)
    return r


def session_by_token(db: Session, token: str) -> TableSession:
    s = db.query(TableSession).filter(TableSession.public_token == token).first()
    if not s:
        raise DomainError("session_not_found", "This table link isn't valid. Scan the QR code again.", 404)
    return s


@router.get("/restaurants/{slug}")
def get_restaurant(slug: str, request: Request, db: Session = Depends(get_db)):
    r = restaurant_by_ref(db, slug)
    return public_restaurant(r, rules_index(db, r.id), demo_now(request)) | {"demo_mode": get_settings().demo_mode}


@router.get("/restaurants/{slug}/menu")
def get_menu(slug: str, request: Request, db: Session = Depends(get_db)):
    r = restaurant_by_ref(db, slug)
    return build_public_menu(db, r, demo_now(request))


@router.get("/menu-items/{item_id}")
def get_item(item_id: str, request: Request, db: Session = Depends(get_db)):
    it = db.get(Item, item_id)
    menu = db.get(Menu, it.menu_id) if it else None
    if not it or menu.status != "published" or it.archived or it.state == "hidden":
        raise DomainError("not_found", "Dish not found.", 404)
    r = db.get(Restaurant, menu.restaurant_id)
    av = evaluate_item(it, it.category, r, rules_index(db, r.id), demo_now(request))
    return serialize_item(it, av) | {"restaurant_slug": r.slug}


def _prefs_with_query(p: Preferences) -> Preferences:
    parsed = rec.parse_query(p.query) if p.query else Preferences()
    merged = p.model_copy(deep=True)
    merged.diets = sorted(set(p.diets) | set(parsed.diets))
    merged.avoid_allergens = sorted(set(a.lower() for a in p.avoid_allergens) | set(parsed.avoid_allergens))
    merged.max_price_minor = p.max_price_minor if p.max_price_minor is not None else parsed.max_price_minor
    merged.max_spice = p.max_spice if p.max_spice is not None else parsed.max_spice
    merged.tastes = sorted(set(p.tastes) | set(parsed.tastes))
    merged.mood = p.mood or parsed.mood
    merged.meal = p.meal or parsed.meal
    return merged


def _rec_view(res: dict) -> dict:
    return {
        "items": [serialize_item(x["item"], x["availability"], promo=x["promo"]) | {"score": x["score"], "reasons": x["reasons"], "boost": x["boost"]} for x in res["results"]],
        "excluded": res["excluded"],
    }


@router.post("/restaurants/{ref}/recommendations", dependencies=[Depends(limit("rec", 40, 60))])
def recommendations(ref: str, prefs: Preferences, request: Request, db: Session = Depends(get_db)):
    r = restaurant_by_ref(db, ref)
    if not merged_config(r.config)["features"]["ai"]:
        raise DomainError("feature_disabled", "Recommendations are turned off for this restaurant.", 403)
    res = rec.rank(db, r, _prefs_with_query(prefs), demo_now(request))
    out = _rec_view(res)
    out["items"] = out["items"][: prefs.limit]
    out["interpreted"] = _prefs_with_query(prefs).model_dump(exclude={"limit", "query"})
    return out


@router.post("/restaurants/{ref}/random-dish", dependencies=[Depends(limit("rand", 40, 60))])
def random_dish(ref: str, prefs: Preferences, request: Request, db: Session = Depends(get_db)):
    r = restaurant_by_ref(db, ref)
    pick = rec.surprise(db, r, _prefs_with_query(prefs), demo_now(request), random.Random())
    if not pick:
        return {"item": None, "message": "Nothing orderable matches right now."}
    return {"item": serialize_item(pick["item"], pick["availability"], promo=pick["promo"]), "reasons": pick["reasons"]}


@router.post("/restaurants/{ref}/chat", dependencies=[Depends(limit("chat", 20, 60))])
def chat(ref: str, body: ChatIn, request: Request, db: Session = Depends(get_db)):
    r = restaurant_by_ref(db, ref)
    if not merged_config(r.config)["features"]["ai"]:
        raise DomainError("feature_disabled", "Ask-a-dish is turned off for this restaurant.", 403)
    return chat_service.answer(db, r, body.message, demo_now(request))


@router.post("/analytics/events", status_code=204, dependencies=[Depends(limit("analytics", 120, 60))])
def analytics(body: AnalyticsIn, request: Request, db: Session = Depends(get_db)):
    r = restaurant_by_ref(db, body.restaurant_slug)
    ref = hashlib.sha256((request.headers.get("x-session-ref") or request.client.host or "").encode()).hexdigest()[:12]
    key = None
    if body.item_id:
        it = db.get(Item, body.item_id)
        key = it.stable_key if it else None
    db.add(AnalyticsEvent(restaurant_id=r.id, event_type=body.event_type, item_key=key, session_ref=ref, is_demo=False))
    db.commit()
    return Response(status_code=204)


# ───────────── QR + table sessions ─────────────
@router.get("/qr/{token}")
def resolve_qr(token: str, db: Session = Depends(get_db)):
    from ..models import QrCode, RestaurantTable

    qr = db.query(QrCode).filter(QrCode.token == token, QrCode.active.is_(True)).first()
    t = db.get(RestaurantTable, qr.table_id) if qr else None
    r = db.get(Restaurant, qr.restaurant_id) if qr else None
    if not qr or not t or t.status != "active" or r.status != "active":
        raise DomainError("qr_invalid", "This QR code isn't active. Ask the staff for help.", 404)
    return {"restaurant_slug": r.slug, "restaurant_name": r.name, "table": t.label, "zone": t.zone}


@router.post("/qr/{token}/session", dependencies=[Depends(limit("qr", 30, 60))])
def open_session(token: str, db: Session = Depends(get_db)):
    s = sess.session_for_qr(db, token)
    return {"session_token": s.public_token, "state": s.state}


def _order_view(o: Order) -> dict:
    return {
        "id": o.id, "number": o.number, "label": o.label, "ticket_type": o.ticket_type, "state": o.state, "created_at": o.created_at.isoformat(),
        "reject_reason": o.reject_reason, "notes": o.notes,
        "items": [{"name": i.name_snapshot, "quantity": i.quantity, "line_total_minor": i.line_total_minor, "modifiers": i.modifiers, "notes": i.notes} for i in o.items],
    }


def _session_view(db: Session, s: TableSession) -> dict:
    r = db.get(Restaurant, s.restaurant_id)
    orders = db.query(Order).filter(Order.session_id == s.id).order_by(Order.ticket_seq).all()
    bill = compute_bill(r, orders)
    pay = db.query(Payment).filter(Payment.session_id == s.id).order_by(Payment.created_at.desc()).first()
    receipt = db.query(Receipt).filter(Receipt.session_id == s.id).first()
    cfg = merged_config(r.config)
    can_order = cfg["features"]["ordering"] and s.state in ("open", "bill_requested") and not (s.state == "bill_requested" and cfg["ordering"]["lock_on_bill_request"])
    return {
        "state": s.state,
        "restaurant": {"slug": r.slug, "name": r.name, "currency": r.currency},
        "table": s.table.label,
        "zone": s.table.zone,
        "contact": {"name": s.contact_name, "phone_masked": mask(s.contact_phone) if s.contact_phone else None, "email_masked": mask(s.contact_email) if s.contact_email else None, "has_contact": bool(s.contact_name and s.contact_phone)},
        "contact_required": cfg["ordering"]["contact_required"],
        "can_order": bool(can_order),
        "orders": [_order_view(o) for o in orders],
        "bill": bill,
        "payment": {"id": pay.id, "state": pay.state, "amount_minor": pay.amount_minor, "simulated": pay.simulated, "failure_reason": pay.failure_reason} if pay else None,
        "receipt_token": receipt.token if receipt else None,
        "demo_mode": get_settings().demo_mode,
    }


@router.get("/table-sessions/{token}")
def get_session(token: str, db: Session = Depends(get_db)):
    return _session_view(db, session_by_token(db, token))


@router.post("/table-sessions/{token}/contact", dependencies=[Depends(limit("contact", 20, 60))])
def set_contact(token: str, body: ContactIn, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    if s.state in ("paid", "closed"):
        raise DomainError("session_locked", "This table is closed.", 409)
    if not body.consent:
        raise DomainError("consent_required", "We need your OK to use these details for your order and receipt.", 422)
    s.contact_name, s.contact_phone = body.name.strip(), body.phone
    s.contact_email = str(body.email).lower() if body.email else None
    s.consent_at = datetime.now(timezone.utc)
    audit(db, "customer", "session.contact_set", s.restaurant_id, "table_session", s.id)  # no PII in audit
    db.commit()
    return _session_view(db, s)


@router.post("/table-sessions/{token}/orders", status_code=201, dependencies=[Depends(limit("order", 30, 60))])
def create_order(token: str, body: OrderIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    order, replayed = order_service.place_order(db, s.id, body, demo_now(request))
    if replayed:
        response.status_code = 200
    db.refresh(s)
    return {"order": _order_view(order), "replayed": replayed, "session": _session_view(db, s)}


@router.get("/table-sessions/{token}/orders")
def list_orders(token: str, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    return [_order_view(o) for o in db.query(Order).filter(Order.session_id == s.id).order_by(Order.ticket_seq).all()]


@router.post("/table-sessions/{token}/bill-request")
def bill_request(token: str, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    sess.request_bill(db, s.id)
    db.refresh(s)
    return _session_view(db, s)


@router.get("/table-sessions/{token}/bill")
def get_bill(token: str, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    r = db.get(Restaurant, s.restaurant_id)
    orders = db.query(Order).filter(Order.session_id == s.id).all()
    return compute_bill(r, orders)


@router.post("/table-sessions/{token}/payment-session", status_code=201)
def payment_session(token: str, body: PaymentSessionIn, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    pay, bill = sess.create_payment_session(db, s.id, body.idempotency_key)
    return {"payment": {"id": pay.id, "state": pay.state, "amount_minor": pay.amount_minor, "currency": pay.currency, "simulated": pay.simulated, "provider": pay.provider}, "bill_version": bill.version}


@router.get("/table-sessions/{token}/payments/{payment_id}")
def payment_status(token: str, payment_id: str, db: Session = Depends(get_db)):
    s = session_by_token(db, token)
    pay = db.get(Payment, payment_id)
    if not pay or pay.session_id != s.id:
        raise DomainError("not_found", "Payment not found.", 404)
    rc = db.query(Receipt).filter(Receipt.payment_id == pay.id).first()
    return {"id": pay.id, "state": pay.state, "amount_minor": pay.amount_minor, "simulated": pay.simulated, "failure_reason": pay.failure_reason, "receipt_token": rc.token if rc else None}


@router.post("/table-sessions/{token}/payments/{payment_id}/simulate")
def simulate_checkout(token: str, payment_id: str, body: MockCheckoutIn, db: Session = Depends(get_db)):
    """Simulated checkout page. Emulates the provider by sending a SIGNED event through the same
    verified webhook handler real providers use; a frontend click alone never marks anything paid."""
    if not get_settings().demo_mode:
        raise DomainError("not_available", "Simulated checkout is disabled.", 404)
    s = session_by_token(db, token)
    pay = db.get(Payment, payment_id)
    if not pay or pay.session_id != s.id or not pay.simulated:
        raise DomainError("not_found", "Payment not found.", 404)
    prov = get_provider(pay.provider)
    assert isinstance(prov, MockPaymentProvider)
    body_bytes, sig = prov.build_event(provider_ref=pay.provider_ref, amount_minor=pay.amount_minor, currency=pay.currency, outcome=body.outcome)
    result = sess.handle_payment_event(db, prov.name, {prov.signature_header: sig}, body_bytes)
    db.refresh(pay)
    return {"result": result, "state": pay.state}


# ───────────── receipts ─────────────
def _receipt_by_token(db: Session, token: str) -> Receipt:
    rc = db.query(Receipt).filter(Receipt.token == token).first()
    exp = rc.expires_at if rc else None
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not rc or rc.revoked or (exp and exp < datetime.now(timezone.utc)):
        raise DomainError("receipt_unavailable", "This receipt link is no longer available.", 404)
    return rc


@router.get("/receipts/{token}")
def get_receipt(token: str, db: Session = Depends(get_db)):
    rc = _receipt_by_token(db, token)
    rv = db.query(Review).filter(Review.receipt_id == rc.id).first()
    return {"number": rc.number, "issued_at": rc.created_at.isoformat(), **rc.data, "review": {"rating": rv.rating, "comment": rv.comment} if rv else None}


@router.post("/receipts/{token}/review", status_code=201, dependencies=[Depends(limit("review", 10, 3600))])
def leave_review(token: str, body: ReviewIn, db: Session = Depends(get_db)):
    """One review per paid receipt; holding the receipt link is the proof of having eaten there."""
    rc = _receipt_by_token(db, token)
    if "refund" in rc.data:
        raise DomainError("refunded", "Reviews can't be left on a refunded bill.", 409)
    if db.query(Review).filter(Review.receipt_id == rc.id).first():
        raise DomainError("already_reviewed", "You've already reviewed this visit. Thank you!", 409)
    r = db.get(Restaurant, rc.restaurant_id)
    db.add(Review(restaurant_id=rc.restaurant_id, receipt_id=rc.id, rating=body.rating, comment=body.comment.strip(), guest_first_name=rc.data.get("guest_first_name"), simulated=bool(r and r.is_demo)))
    audit(db, "customer", "review.created", rc.restaurant_id, "receipt", rc.id, {"rating": body.rating})
    db.commit()
    return {"rating": body.rating, "comment": body.comment.strip()}


@router.get("/media/{path:path}")
def media(path: str):
    """Serves only re-encoded dish photos."""
    if not path.startswith("dishes/") or not path.endswith(".jpg"):
        raise DomainError("not_found", "Not found.", 404)
    from ..providers.storage import get_storage
    try:
        f = get_storage().path(path)
    except ValueError:
        raise DomainError("not_found", "Not found.", 404)
    if not f.is_file():
        raise DomainError("not_found", "Not found.", 404)
    return Response(f.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/receipts/{token}/pdf")
def receipt_pdf(token: str, db: Session = Depends(get_db)):
    rc = _receipt_by_token(db, token)
    d, bill = rc.data, rc.data["bill"]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A6)
    w, h = A6
    y = h - 28
    sym = "Rs." if bill["currency"] == "INR" else bill["currency"] + " "
    m = lambda v: f"{sym}{v / 100:,.2f}"
    c.setFont("Helvetica-Bold", 13); c.drawString(18, y, d["restaurant"]["name"][:34]); y -= 14
    c.setFont("Helvetica", 8); c.drawString(18, y, f"Receipt {rc.number}  |  Table {d['table']}"); y -= 10
    c.drawString(18, y, f"Paid {d['payment']['paid_at'][:16].replace('T', ' ')} UTC" + ("  (SIMULATED)" if d["payment"]["simulated"] else "")); y -= 16
    for t in bill["tickets"]:
        for i in t["items"]:
            if y < 70:
                c.showPage(); y = h - 30
            c.drawString(18, y, f"{i['quantity']} x {i['name']}"[:38]); c.drawRightString(w - 18, y, m(i["line_total_minor"])); y -= 10
    y -= 4
    for label, v in [("Subtotal", bill["subtotal_minor"]), ("Service charge", bill["service_charge_minor"]), (f"{bill['tax_label']}{' (incl.)' if bill['tax_inclusive'] else ''}", bill["tax_minor"]), ("Rounding", bill["rounding_minor"])]:
        if v or label == "Subtotal":
            c.drawString(18, y, label); c.drawRightString(w - 18, y, m(v)); y -= 10
    c.setFont("Helvetica-Bold", 10); c.drawString(18, y - 4, "Total"); c.drawRightString(w - 18, y - 4, m(bill["total_minor"]))
    c.save()
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{rc.number}.pdf"'})


@router.get("/demo/directory")
def demo_directory(db: Session = Depends(get_db)):
    """Landing-page helper: only exists in DEMO_MODE and only lists sample restaurants."""
    if not get_settings().demo_mode:
        raise DomainError("not_found", "Not found.", 404)
    from ..models import QrCode, RestaurantTable

    out = []
    for r in db.query(Restaurant).filter(Restaurant.is_demo.is_(True), Restaurant.status == "active").order_by(Restaurant.name).all():
        tabs = []
        for t in db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == r.id).all():
            qr = db.query(QrCode).filter(QrCode.table_id == t.id, QrCode.active.is_(True)).first()
            if qr:
                tabs.append({"label": t.label, "zone": t.zone, "qr_token": qr.token})
        out.append({"slug": r.slug, "name": r.name, "tagline": r.tagline, "cuisine": r.cuisine, "theme": merged_theme(r.theme), "tables": sorted(tabs, key=lambda x: (len(x["label"]), x["label"]))})
    return out
