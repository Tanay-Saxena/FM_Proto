"""Table session lifecycle, bill snapshots, payment sessions and verified payment events."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import critical_section, lock_row
from ..defaults import merged_config
from ..models import Bill, Order, Payment, PaymentEvent, QrCode, Receipt, Restaurant, RestaurantTable, TableSession
from ..providers.payments import WebhookVerificationError, get_provider
from ..security import public_token
from .audit import audit
from .billing import compute_bill
from .errors import DomainError
from .receipts import create_receipt

LIVE_STATES = ("open", "bill_requested", "payment_pending")


def session_for_qr(db: Session, qr_token: str) -> TableSession:
    """Resolve a table QR to the table's live session, creating one if the table is free."""
    with critical_section():
        qr = db.query(QrCode).filter(QrCode.token == qr_token, QrCode.active.is_(True)).first()
        table = db.get(RestaurantTable, qr.table_id) if qr else None
        if not qr or not table or table.status != "active":
            raise DomainError("qr_invalid", "This QR code isn't active. Ask the staff for help.", 404)
        restaurant = db.get(Restaurant, qr.restaurant_id)
        if restaurant.status != "active":
            raise DomainError("restaurant_inactive", "This restaurant isn't available.", 403)
        s = (
            db.query(TableSession)
            .filter(TableSession.table_id == table.id, TableSession.state.in_(LIVE_STATES))
            .order_by(TableSession.opened_at.desc())
            .first()
        )
        if not s:
            s = TableSession(restaurant_id=restaurant.id, table_id=table.id, public_token=public_token(24), state="open")
            db.add(s)
            audit(db, "customer", "session.opened", restaurant.id, "table_session", s.id, {"table": table.label})
            db.commit()
        return s


def active_bill(db: Session, session: TableSession, restaurant: Restaurant) -> Bill:
    """Recompute the bill from authoritative orders; reuse the active snapshot if nothing changed."""
    orders = db.query(Order).filter(Order.session_id == session.id).all()
    data = compute_bill(restaurant, orders)
    cur = db.query(Bill).filter(Bill.session_id == session.id, Bill.status == "active").order_by(Bill.version.desc()).first()
    if cur and cur.data == data:
        return cur
    if cur:
        cur.status = "superseded"
    version = (db.query(func.max(Bill.version)).filter(Bill.session_id == session.id).scalar() or 0) + 1
    bill = Bill(restaurant_id=restaurant.id, session_id=session.id, version=version, status="active", data=data, total_minor=data["total_minor"], currency=data["currency"])
    db.add(bill)
    db.flush()
    return bill


def request_bill(db: Session, session_id: str) -> Bill:
    with critical_section():
        s = lock_row(db, TableSession, session_id)
        r = db.get(Restaurant, s.restaurant_id)
        if s.state in ("paid", "closed"):
            raise DomainError("already_paid", "This table's bill has already been paid.", 409)
        bill = active_bill(db, s, r)
        if bill.total_minor <= 0:
            raise DomainError("nothing_to_bill", "There's nothing to pay yet. Place an order first.", 409)
        if s.state == "open":
            s.state = "bill_requested"
            audit(db, "customer", "session.bill_requested", r.id, "table_session", s.id, {"total": bill.total_minor})
        db.commit()
        return bill


def create_payment_session(db: Session, session_id: str, idempotency_key: str) -> tuple[Payment, Bill]:
    with critical_section():
        s = lock_row(db, TableSession, session_id)
        r = db.get(Restaurant, s.restaurant_id)
        prior = db.query(Payment).filter(Payment.idempotency_key == idempotency_key).first()
        if prior:
            if prior.session_id != s.id:
                raise DomainError("idempotency_conflict", "That request key was used for another table.", 409)
            return prior, db.get(Bill, prior.bill_id)
        if s.state in ("paid", "closed"):
            raise DomainError("already_paid", "This table's bill has already been paid.", 409)
        if s.state == "payment_pending":
            pending = db.query(Payment).filter(Payment.session_id == s.id, Payment.state == "pending").order_by(Payment.created_at.desc()).first()
            if pending:
                return pending, db.get(Bill, pending.bill_id)
        bill = active_bill(db, s, r)
        if bill.total_minor <= 0:
            raise DomainError("nothing_to_bill", "There's nothing to pay yet.", 409)
        provider = get_provider()
        created = provider.create_payment(payment_id=s.id, amount_minor=bill.total_minor, currency=bill.currency, reference=f"{r.slug}-{s.id[:8]}")
        pay = Payment(
            restaurant_id=r.id, session_id=s.id, bill_id=bill.id, provider=provider.name, provider_ref=created["provider_ref"],
            amount_minor=bill.total_minor, currency=bill.currency, state="pending", idempotency_key=idempotency_key, simulated=provider.simulated,
        )
        db.add(pay)
        s.state = "payment_pending"  # locks further ordering
        audit(db, "customer", "payment.created", r.id, "payment", pay.id, {"amount": pay.amount_minor, "bill_version": bill.version, "simulated": pay.simulated})
        db.commit()
        return pay, bill


def release_payment_lock(db: Session, session_id: str, actor: str) -> TableSession:
    """Staff action: abandon pending payments and return the table to a payable state (audited)."""
    with critical_section():
        s = lock_row(db, TableSession, session_id)
        if s.state != "payment_pending":
            raise DomainError("invalid_state", "This table isn't waiting on a payment.", 409)
        for p in db.query(Payment).filter(Payment.session_id == s.id, Payment.state == "pending").all():
            p.state, p.failure_reason = "cancelled", "released by staff"
        s.state = "bill_requested"
        audit(db, actor, "session.payment_lock_released", s.restaurant_id, "table_session", s.id)
        db.commit()
        return s


def close_session(db: Session, session_id: str, actor: str, *, force: bool = False, reason: str = "") -> TableSession:
    with critical_section():
        s = lock_row(db, TableSession, session_id)
        if s.state == "closed":
            return s
        if s.state != "paid" and not force:
            raise DomainError("unpaid", "This table hasn't paid. Only a manager can close it without payment.", 409)
        if s.state != "paid":
            if not reason:
                raise DomainError("reason_required", "Add a reason for closing without payment.", 422)
            active = db.query(Order).filter(Order.session_id == s.id, Order.state.in_(["submitted", "accepted", "preparing", "ready"])).count()
            if active:
                raise DomainError("orders_active", "Some tickets are still in the kitchen. Cancel or serve them first.", 409)
            for p in db.query(Payment).filter(Payment.session_id == s.id, Payment.state == "pending").all():
                p.state, p.failure_reason = "cancelled", "session closed by staff"
        s.state, s.closed_at = "closed", datetime.now(timezone.utc)
        audit(db, actor, "session.closed", s.restaurant_id, "table_session", s.id, {"forced": force, "reason": reason})
        db.commit()
        return s


def reopen_session(db: Session, session_id: str, actor: str) -> TableSession:
    """Re-open a table that staff closed WITHOUT payment (e.g. closed by mistake). Paid sessions stay closed."""
    with critical_section():
        s = lock_row(db, TableSession, session_id)
        if s.state != "closed":
            raise DomainError("not_closed", "Only a closed table can be re-opened.", 409)
        if db.query(Payment).filter(Payment.session_id == s.id, Payment.state.in_(["succeeded", "refunded"])).count():
            raise DomainError("already_paid", "This table was paid. Start a new session instead.", 409)
        if db.query(TableSession).filter(TableSession.table_id == s.table_id, TableSession.state.in_(LIVE_STATES)).count():
            raise DomainError("table_busy", "Another party is already at this table.", 409)
        s.state, s.closed_at = "open", None
        audit(db, actor, "session.reopened", s.restaurant_id, "table_session", s.id)
        db.commit()
        return s


def transfer_session(db: Session, session_id: str, to_table_id: str, actor: str) -> TableSession:
    """Move a live party to a free table. Orders and the bill follow the session; the QR guests hold stays valid."""
    with critical_section():
        s = lock_row(db, TableSession, session_id)
        if s.state not in ("open", "bill_requested"):
            raise DomainError("not_transferable", "Only a table that is ordering or has requested the bill can be moved.", 409)
        dest = db.get(RestaurantTable, to_table_id)
        if not dest or dest.restaurant_id != s.restaurant_id or dest.status != "active":
            raise DomainError("not_found", "Destination table not found.", 404)
        if dest.id == s.table_id:
            raise DomainError("same_table", "That's the current table.", 422)
        if db.query(TableSession).filter(TableSession.table_id == dest.id, TableSession.state.in_(LIVE_STATES)).count():
            raise DomainError("table_busy", "That table already has guests.", 409)
        old = s.table.label
        s.table_id = dest.id
        audit(db, actor, "session.transferred", s.restaurant_id, "table_session", s.id, {"from": old, "to": dest.label})
        db.commit()
        db.refresh(s)
        return s


def refund_payment(db: Session, payment_id: str, restaurant_id: str, actor: str, reason: str) -> Payment:
    """Full refund of a succeeded payment through the provider adapter. Partial refunds are not built."""
    with critical_section():
        p = lock_row(db, Payment, payment_id)
        if p.restaurant_id != restaurant_id:
            raise DomainError("not_found", "Payment not found.", 404)
        if p.state == "refunded":
            return p
        if p.state != "succeeded":
            raise DomainError("not_refundable", "Only a completed payment can be refunded.", 409)
        if not reason.strip():
            raise DomainError("reason_required", "Add a reason for the refund.", 422)
        out = get_provider(p.provider).refund(provider_ref=p.provider_ref, amount_minor=p.amount_minor, currency=p.currency, reason=reason)
        p.state, p.refunded_minor, p.refunded_at, p.refund_reason, p.refund_ref = "refunded", p.amount_minor, datetime.now(timezone.utc), reason[:200], out["refund_ref"]
        rc = db.query(Receipt).filter(Receipt.payment_id == p.id).first()
        if rc:
            rc.data = {**rc.data, "refund": {"amount_minor": p.refunded_minor, "refunded_at": p.refunded_at.isoformat(), "reason": p.refund_reason, "simulated": bool(out.get("simulated"))}}
        audit(db, actor, "payment.refunded", restaurant_id, "payment", p.id, {"amount": p.amount_minor, "reason": reason[:200], "ref": p.refund_ref})
        db.commit()
        return p


def handle_payment_event(db: Session, provider_name: str, headers, body: bytes) -> dict:
    """The ONLY path that can mark a bill paid. Verifies authenticity, dedupes, reconciles, then applies."""
    try:
        provider = get_provider(provider_name)
    except KeyError:
        raise DomainError("unknown_provider", "Unknown payment provider.", 404)
    try:
        event = provider.verify_webhook(headers, body)
    except WebhookVerificationError as e:
        audit(db, "webhook", "payment.webhook_rejected", None, "payment_event", "", {"provider": provider_name, "why": str(e)})
        db.commit()
        raise DomainError("bad_signature", "Webhook verification failed.", 400)

    with critical_section():
        dup = db.query(PaymentEvent).filter(PaymentEvent.provider == provider.name, PaymentEvent.event_id == event["event_id"]).first()
        if dup:
            return {"status": "duplicate", "outcome": dup.outcome}
        pay = db.query(Payment).filter(Payment.provider_ref == event["provider_ref"], Payment.provider == provider.name).first()
        ev = PaymentEvent(provider=provider.name, event_id=event["event_id"], event_type=event["type"], payment_id=pay.id if pay else None, restaurant_id=pay.restaurant_id if pay else None, verified=True, payload={k: event.get(k) for k in ("type", "provider_ref", "amount_minor", "currency")})
        db.add(ev)
        if not pay:
            ev.outcome = "unknown_payment"
            db.commit()
            return {"status": "ignored", "outcome": ev.outcome}

        session = lock_row(db, TableSession, pay.session_id)
        restaurant = db.get(Restaurant, pay.restaurant_id)
        etype = event["type"]

        if etype == "payment.succeeded":
            bill = db.get(Bill, pay.bill_id)
            if event.get("amount_minor") != pay.amount_minor or event.get("currency") != pay.currency or pay.amount_minor != bill.total_minor:
                ev.outcome = "amount_mismatch"
                audit(db, "webhook", "payment.amount_mismatch", restaurant.id, "payment", pay.id, {"expected": pay.amount_minor, "got": event.get("amount_minor")})
                db.commit()
                return {"status": "rejected", "outcome": ev.outcome}
            if pay.state == "succeeded":
                ev.outcome = "already_succeeded"
                db.commit()
                return {"status": "duplicate", "outcome": ev.outcome}
            if session.state in ("paid", "closed") and db.query(Payment).filter(Payment.session_id == session.id, Payment.state == "succeeded").count():
                pay.state, pay.failure_reason = "refund_pending", "Duplicate payment for an already-paid bill — refund required"
                ev.outcome = "duplicate_payment_refund_required"
                audit(db, "webhook", "payment.duplicate_charge", restaurant.id, "payment", pay.id)
                db.commit()
                return {"status": "flagged", "outcome": ev.outcome}
            pay.state, pay.failure_reason = "succeeded", None
            pay.paid_at = datetime.now(timezone.utc)
            bill.status = "paid"
            session.state = "paid"
            receipt = create_receipt(db, session, pay, bill.data)
            audit(db, "webhook", "payment.succeeded", restaurant.id, "payment", pay.id, {"amount": pay.amount_minor, "receipt": receipt.number})
            if merged_config(restaurant.config)["ordering"]["auto_close_after_payment"]:
                session.state, session.closed_at = "closed", datetime.now(timezone.utc)
                audit(db, "system", "session.closed", restaurant.id, "table_session", session.id, {"auto": True})
            ev.outcome = "applied"
        elif etype in ("payment.failed", "payment.cancelled"):
            if pay.state in ("succeeded", "refund_pending", "refunded"):
                ev.outcome = "ignored_after_success"
            else:
                pay.state = "failed" if etype == "payment.failed" else "cancelled"
                pay.failure_reason = "Payment was declined" if etype == "payment.failed" else "Cancelled at checkout"
                db.flush()
                if session.state == "payment_pending" and not db.query(Payment).filter(Payment.session_id == session.id, Payment.state == "pending").count():
                    session.state = "bill_requested"  # payable again, ordering reopens
                audit(db, "webhook", f"payment.{pay.state}", restaurant.id, "payment", pay.id)
                ev.outcome = "applied"
        else:
            ev.outcome = "ignored_type"
        db.commit()
        return {"status": "ok", "outcome": ev.outcome}
