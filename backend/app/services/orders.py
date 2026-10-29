"""Order placement (original + add-on tickets) and the kitchen state machine."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import critical_section, lock_row
from ..defaults import merged_config
from ..models import Bill, Order, OrderItem, OrderStatusEvent, Restaurant, TableSession
from ..schemas import OrderIn
from .audit import audit
from .availability import evaluate_item
from .errors import DomainError
from .menu import find_item, published_menu, rules_index

ORDERABLE_SESSION_STATES = {"open", "bill_requested"}

# Explicit transition table — no generic PATCH of status anywhere.
TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"accepted", "rejected", "cancelled"},
    "accepted": {"preparing", "rejected", "cancelled"},
    "preparing": {"ready", "cancelled"},
    "ready": {"served", "cancelled"},
    "served": set(),
    "rejected": set(),
    "cancelled": set(),
}
KITCHEN_TARGETS = {"accepted", "preparing", "ready", "served", "rejected"}  # 'cancelled' needs orders.cancel
ACTIVE_STATES = {"submitted", "accepted", "preparing", "ready"}


def _next_event_seq(db: Session, restaurant_id: str) -> int:
    return (db.query(func.max(OrderStatusEvent.seq)).filter(OrderStatusEvent.restaurant_id == restaurant_id).scalar() or 0) + 1


def _record(db: Session, order: Order, from_state: str | None, to_state: str, actor: str):
    db.add(OrderStatusEvent(order_id=order.id, restaurant_id=order.restaurant_id, from_state=from_state, to_state=to_state, actor=actor, seq=_next_event_seq(db, order.restaurant_id)))
    db.flush()


def place_order(db: Session, session_id: str, payload: OrderIn, now: datetime) -> tuple[Order, bool]:
    """Returns (order, replayed). Everything is validated server-side; the client sends item ids only."""
    with critical_section():
        session = lock_row(db, TableSession, session_id)
        replay = db.query(Order).filter(Order.session_id == session.id, Order.idempotency_key == payload.idempotency_key).first()
        if replay:
            return replay, True

        restaurant = db.get(Restaurant, session.restaurant_id)
        cfg = merged_config(restaurant.config)
        if restaurant.status != "active":
            raise DomainError("restaurant_inactive", "This restaurant isn't taking orders.", 403)
        if not cfg["features"]["ordering"]:
            raise DomainError("ordering_disabled", "Ordering from the table isn't enabled for this restaurant.", 403)
        if session.state not in ORDERABLE_SESSION_STATES:
            raise DomainError("session_locked", "This table's bill is being paid or is closed, so new items can't be added.", 409)
        if session.state == "bill_requested" and cfg["ordering"]["lock_on_bill_request"]:
            raise DomainError("session_locked", "The bill has been requested, so ordering is locked.", 409)
        if cfg["ordering"]["contact_required"] and not (session.contact_name and session.contact_phone):
            raise DomainError("contact_required", "Add your name and mobile number before ordering.", 422)

        menu = published_menu(db, restaurant.id)
        if not menu:
            raise DomainError("no_menu", "No published menu.", 409)
        idx = rules_index(db, restaurant.id)

        resolved, unavailable = [], []
        qty_by_item: dict[str, int] = {}
        for line in payload.lines:
            item, cat = find_item(menu, line.item_id)
            if not item:
                raise DomainError("item_not_found", "One of the items isn't on this restaurant's menu.", 422, {"item_id": line.item_id})
            av = evaluate_item(item, cat, restaurant, idx, now)
            if not av.orderable:
                unavailable.append({"item_id": item.id, "name": item.name, "status": av.status, "message": av.message})
                continue
            mods, delta = [], 0
            chosen = set(line.modifier_option_ids)
            known = set()
            for g in item.modifier_groups:
                opts = {o["id"]: o for o in g["options"]}
                known |= set(opts)
                picked = [opts[i] for i in chosen if i in opts]
                if len(picked) < g.get("min", 0) or len(picked) > g.get("max", 1):
                    raise DomainError("modifier_invalid", f"Choose {g.get('min', 0)}–{g.get('max', 1)} option(s) for “{g['name']}” on {item.name}.", 422)
                for o in picked:
                    mods.append({"group": g["name"], "name": o["name"], "price_minor": o["price_minor"]})
                    delta += o["price_minor"]
            if chosen - known:
                raise DomainError("modifier_invalid", f"Unknown option for {item.name}.", 422)
            qty_by_item[item.id] = qty_by_item.get(item.id, 0) + line.quantity
            resolved.append((item, line, mods, delta))
        if unavailable:
            raise DomainError("items_unavailable", "Some items are no longer available. Remove them to continue.", 409, unavailable)

        for item, _, _, _ in resolved:
            if item.stock_remaining is not None and qty_by_item.get(item.id, 0) > item.stock_remaining:
                raise DomainError("insufficient_stock", f"Only {item.stock_remaining} left of {item.name}.", 409, [{"item_id": item.id, "name": item.name, "available": item.stock_remaining}])
        seen = set()
        for item, *_ in resolved:
            if item.id not in seen and item.stock_remaining is not None:
                item.stock_remaining -= qty_by_item[item.id]
            seen.add(item.id)

        number = (db.query(func.max(Order.number)).filter(Order.restaurant_id == restaurant.id).scalar() or 1000) + 1
        session.ticket_seq += 1
        order = Order(
            restaurant_id=restaurant.id, session_id=session.id, number=number, ticket_seq=session.ticket_seq,
            ticket_type="original" if session.ticket_seq == 1 else "addon", state="submitted",
            notes=payload.notes, idempotency_key=payload.idempotency_key,
        )
        db.add(order)
        db.flush()
        for item, line, mods, delta in resolved:
            unit = item.price_minor + delta
            db.add(OrderItem(order_id=order.id, item_id=item.id, stable_key=item.stable_key, name_snapshot=item.name, unit_price_minor=unit, quantity=line.quantity, modifiers=mods, notes=line.notes, line_total_minor=unit * line.quantity))
        _record(db, order, None, "submitted", "customer")

        if session.state == "bill_requested":
            session.state = "open"  # new items invalidate the requested bill
            db.query(Bill).filter(Bill.session_id == session.id, Bill.status == "active").update({"status": "superseded"})
            audit(db, "customer", "session.reopened_by_addon", restaurant.id, "table_session", session.id, {"order": number})
        audit(db, "customer", "order.placed", restaurant.id, "order", order.id, {"number": number, "ticket": order.label, "type": order.ticket_type})
        db.commit()
        db.refresh(order)
        return order, False


def transition(db: Session, order_id: str, to_state: str, actor: str, *, can_cancel: bool, reason: str = "") -> Order:
    with critical_section():
        order = lock_row(db, Order, order_id)
        session = db.get(TableSession, order.session_id)
        if to_state == "cancelled" and not can_cancel:
            audit(db, actor, "order.transition_denied", order.restaurant_id, "order", order.id, {"to": to_state, "why": "permission"})
            db.commit()
            raise DomainError("forbidden", "Only a manager or owner can cancel a ticket.", 403)
        if to_state not in TRANSITIONS.get(order.state, set()):
            audit(db, actor, "order.transition_denied", order.restaurant_id, "order", order.id, {"from": order.state, "to": to_state, "why": "invalid"})
            db.commit()
            raise DomainError("invalid_transition", f"A {order.state} ticket can't move to {to_state}.", 409)
        if to_state in ("rejected", "cancelled"):
            if session.state in ("payment_pending", "paid", "closed"):
                raise DomainError("session_locked", "The bill is already being paid, so this ticket can't be removed. Ask a manager to release the payment lock first.", 409)
            if not reason:
                raise DomainError("reason_required", "Add a reason so the guest can be told.", 422)
        prev = order.state
        order.state = to_state
        if to_state in ("rejected", "cancelled"):
            order.reject_reason = reason
            _restore_stock(db, order)
            if session.state == "bill_requested":
                session.state = "open"
                db.query(Bill).filter(Bill.session_id == session.id, Bill.status == "active").update({"status": "superseded"})
        _record(db, order, prev, to_state, actor)
        audit(db, actor, "order.transition", order.restaurant_id, "order", order.id, {"from": prev, "to": to_state, "reason": reason})
        db.commit()
        db.refresh(order)
        return order


def _restore_stock(db: Session, order: Order):
    from ..models import Item

    for oi in order.items:
        if oi.item_id:
            it = db.get(Item, oi.item_id)
            if it and it.stock_remaining is not None:
                it.stock_remaining += oi.quantity


def serialize_order(o: Order, include_table=True) -> dict:
    s = o.session
    return {
        "id": o.id,
        "number": o.number,
        "label": o.label,
        "ticket_type": o.ticket_type,
        "ticket_seq": o.ticket_seq,
        "state": o.state,
        "notes": o.notes,
        "reject_reason": o.reject_reason,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "session_id": o.session_id,
        "table": s.table.label if include_table and s and s.table else None,
        "zone": s.table.zone if include_table and s and s.table else None,
        "session_state": s.state if s else None,
        "guest": (s.contact_name or "").split(" ")[0] if s else None,
        "items": [{"name": i.name_snapshot, "quantity": i.quantity, "unit_price_minor": i.unit_price_minor, "line_total_minor": i.line_total_minor, "modifiers": i.modifiers, "notes": i.notes} for i in o.items],
        "total_minor": sum(i.line_total_minor for i in o.items),
        "events": [{"from": e.from_state, "to": e.to_state, "actor": e.actor, "at": e.at.isoformat()} for e in o.events],
    }
