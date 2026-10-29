"""Restaurant admin API. Every route resolves membership + permission in the backend (deps.require)."""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

import segno
from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal, get_db
from ..defaults import DEFAULT_CONFIG, merged_config, merged_theme
from ..deps import Access, access_for, current_user, demo_now, has_perm, platform_admin, require
from ..models import *  # noqa
from ..schemas import *  # noqa
from ..security import hash_password, public_token
from ..services import ingestion as ing
from ..services import orders as order_service
from ..services import sessions as sess
from ..services.audit import audit
from ..services.availability import evaluate_item
from ..services.billing import compute_bill
from ..services.errors import DomainError
from ..services.menu import rules_index, serialize_item
from ..services.menu_admin import clone_menu, publish_menu
from ..services.receipts import deliver, mask
from ..providers.storage import get_storage

router = APIRouter()


def _iso(d):
    return d.isoformat() if d else None


# ───────── restaurants ─────────
@router.post("/restaurants", status_code=201)
def create_restaurant(body: RestaurantCreate, admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    if db.query(Restaurant).filter(Restaurant.slug == body.slug).first():
        raise DomainError("slug_taken", "That web address is taken.", 409)
    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise DomainError("bad_timezone", "Unknown timezone.", 422)
    r = Restaurant(slug=body.slug, name=body.name, venue_type=body.venue_type, cuisine=body.cuisine, timezone=body.timezone, currency=body.currency.upper(), theme=merged_theme({}), config=DEFAULT_CONFIG)
    db.add(r)
    db.flush()
    owner = db.query(User).filter(User.email == body.owner_email.lower()).first()
    if not owner:
        owner = User(email=body.owner_email.lower(), name="", password_hash=hash_password(body.owner_password))
        db.add(owner)
        db.flush()
    db.add(Membership(user_id=owner.id, restaurant_id=r.id, role="owner"))
    m = Menu(restaurant_id=r.id, name="Main menu", version=1, status="published", published_at=datetime.now(timezone.utc))
    db.add(m)
    audit(db, admin.email, "restaurant.created", r.id, "restaurant", r.id)
    db.commit()
    return {"id": r.id, "slug": r.slug}


def _sanitize_config(patch: dict) -> dict:
    out: dict = {}
    f = patch.get("features")
    if isinstance(f, dict):
        out["features"] = {k: bool(v) for k, v in f.items() if k in DEFAULT_CONFIG["features"]}
    t = patch.get("tax")
    if isinstance(t, dict):
        tx = {}
        if "gst_bps" in t:
            tx["gst_bps"] = max(0, min(5000, int(t["gst_bps"])))
        if "inclusive" in t:
            tx["inclusive"] = bool(t["inclusive"])
        if "label" in t:
            tx["label"] = str(t["label"])[:20]
        out["tax"] = tx
    if "service_charge_bps" in patch:
        out["service_charge_bps"] = max(0, min(3000, int(patch["service_charge_bps"])))
    if "round_to_rupee" in patch:
        out["round_to_rupee"] = bool(patch["round_to_rupee"])
    o = patch.get("ordering")
    if isinstance(o, dict):
        out["ordering"] = {k: bool(v) for k, v in o.items() if k in DEFAULT_CONFIG["ordering"]}
    if patch.get("card_density") in ("comfortable", "compact"):
        out["card_density"] = patch["card_density"]
    tp = patch.get("templates")
    if isinstance(tp, dict):
        out["templates"] = {k: str(v)[:400] for k, v in tp.items() if k in DEFAULT_CONFIG["templates"]}
    return out


@router.get("/restaurants/{restaurant_id}/settings")
def get_restaurant(a: Access = Depends(require("settings.view"))):
    r = a.restaurant
    return {"id": r.id, "slug": r.slug, "name": r.name, "tagline": r.tagline, "cuisine": r.cuisine, "venue_type": r.venue_type, "timezone": r.timezone, "currency": r.currency, "theme": merged_theme(r.theme), "config": merged_config(r.config), "is_demo": r.is_demo, "role": a.role}


@router.patch("/restaurants/{restaurant_id}")
def patch_restaurant(body: RestaurantPatch, a: Access = Depends(require("settings.edit")), db: Session = Depends(get_db)):
    r = a.restaurant
    for f in ("name", "tagline", "cuisine"):
        v = getattr(body, f)
        if v is not None:
            setattr(r, f, v)
    if body.timezone:
        if body.timezone not in available_timezones():
            raise DomainError("bad_timezone", "Unknown timezone.", 422)
        r.timezone = body.timezone
    if body.currency:
        r.currency = body.currency.upper()
    if body.theme:
        r.theme = body.theme.model_dump()
    if body.config:
        clean = _sanitize_config(body.config)
        cur = merged_config(r.config)
        for k, v in clean.items():
            cur[k] = {**cur[k], **v} if isinstance(v, dict) else v
        r.config = cur
    audit(db, a.actor, "restaurant.updated", r.id, "restaurant", r.id, {"fields": list(body.model_dump(exclude_none=True))})
    db.commit()
    return get_restaurant(a)


# ───────── menus ─────────
def _menu_for(db, a: Access, menu_id: str) -> Menu:
    m = db.get(Menu, menu_id)
    if not m or m.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Menu not found.", 404)
    return m


def _item_for(db, a: Access, item_id: str) -> Item:
    it = db.get(Item, item_id)
    if not it or db.get(Menu, it.menu_id).restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Dish not found.", 404)
    return it


@router.get("/restaurants/{restaurant_id}/menus")
def list_menus(a: Access = Depends(require("menu.view")), db: Session = Depends(get_db)):
    ms = db.query(Menu).filter(Menu.restaurant_id == a.restaurant.id).order_by(Menu.version.desc()).all()
    return [{"id": m.id, "name": m.name, "version": m.version, "status": m.status, "published_at": _iso(m.published_at), "item_count": sum(1 for c in m.categories for i in c.items if not i.archived)} for m in ms]


@router.get("/restaurants/{restaurant_id}/menus/{menu_id}")
def get_admin_menu(menu_id: str, request: Request, a: Access = Depends(require("menu.view")), db: Session = Depends(get_db)):
    m = _menu_for(db, a, menu_id)
    idx, now = rules_index(db, a.restaurant.id), demo_now(request)
    return {"id": m.id, "status": m.status, "version": m.version, "name": m.name, "categories": [
        {"id": c.id, "key": c.stable_key, "name": c.name, "description": c.description, "sort": c.sort, "items": [
            serialize_item(i, evaluate_item(i, c, a.restaurant, idx, now)) | {"state": i.state, "archived": i.archived, "sort": i.sort, "stock_remaining": i.stock_remaining}
            for i in c.items]} for c in m.categories]}


@router.post("/restaurants/{restaurant_id}/menus/{menu_id}/clone", status_code=201)
def clone(menu_id: str, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    m = _menu_for(db, a, menu_id)
    d = clone_menu(db, m, a.restaurant.id, name=f"Draft of v{m.version}")
    audit(db, a.actor, "menu.cloned", a.restaurant.id, "menu", d.id)
    db.commit()
    return {"id": d.id, "version": d.version}


@router.post("/restaurants/{restaurant_id}/menus/{menu_id}/publish")
def publish(menu_id: str, a: Access = Depends(require("menu.publish")), db: Session = Depends(get_db)):
    m = publish_menu(db, _menu_for(db, a, menu_id), a.actor)
    return {"id": m.id, "version": m.version, "status": m.status}


@router.post("/restaurants/{restaurant_id}/menus/{menu_id}/categories", status_code=201)
def add_category(menu_id: str, body: CategoryIn, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    m = _menu_for(db, a, menu_id)
    c = Category(menu_id=m.id, name=body.name, description=body.description, sort=body.sort if body.sort is not None else len(m.categories))
    db.add(c)
    audit(db, a.actor, "category.created", a.restaurant.id, "category", c.id, {"name": c.name})
    db.commit()
    return {"id": c.id, "key": c.stable_key}


@router.patch("/restaurants/{restaurant_id}/categories/{category_id}")
def patch_category(category_id: str, body: CategoryIn, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    c = db.get(Category, category_id)
    if not c or _menu_for(db, a, c.menu_id) is None:
        raise DomainError("not_found", "Category not found.", 404)
    c.name, c.description = body.name, body.description
    if body.sort is not None:
        c.sort = body.sort
    audit(db, a.actor, "category.updated", a.restaurant.id, "category", c.id)
    db.commit()
    return {"id": c.id}


@router.delete("/restaurants/{restaurant_id}/categories/{category_id}", status_code=204)
def delete_category(category_id: str, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    c = db.get(Category, category_id)
    if not c or _menu_for(db, a, c.menu_id) is None:
        raise DomainError("not_found", "Category not found.", 404)
    if any(not i.archived for i in c.items):
        raise DomainError("category_not_empty", "Move or archive this category's dishes first.", 409)
    audit(db, a.actor, "category.deleted", a.restaurant.id, "category", c.id, {"name": c.name})
    db.delete(c)
    db.commit()
    return Response(status_code=204)


@router.post("/restaurants/{restaurant_id}/menus/{menu_id}/reorder")
def reorder_menu(menu_id: str, body: ReorderIn, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    """Persist a new order for categories (kind=categories) or for the dishes inside one category (kind=items)."""
    m = _menu_for(db, a, menu_id)
    if body.kind == "categories":
        by_id = {c.id: c for c in m.categories}
        if set(body.ids) != set(by_id):
            raise DomainError("bad_order", "The list must contain every category exactly once.", 422)
        for n, cid in enumerate(body.ids):
            by_id[cid].sort = n
    else:
        cat = db.get(Category, body.category_id or "")
        if not cat or cat.menu_id != m.id:
            raise DomainError("bad_category", "Pick a category from this menu.", 422)
        by_id = {i.id: i for i in cat.items}
        if set(body.ids) != set(by_id):
            raise DomainError("bad_order", "The list must contain every dish in the category exactly once.", 422)
        for n, iid in enumerate(body.ids):
            by_id[iid].sort = n
    audit(db, a.actor, "menu.reordered", a.restaurant.id, "menu", m.id, {"kind": body.kind})
    db.commit()
    return {"ok": True}


@router.post("/restaurants/{restaurant_id}/items/{item_id}/image")
async def upload_item_image(item_id: str, file: UploadFile = File(...), a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    """Real dish photo. The upload is decoded and re-encoded (EXIF/GPS stripped, max 1200px), never served as sent."""
    it = _item_for(db, a, item_id)
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise DomainError("too_large", "Photos can be up to 5 MB.", 413)
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise DomainError("bad_image", "Use a JPEG, PNG or WebP photo.", 422)
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise DomainError("bad_image", "That file isn't a readable image.", 422)
    img.thumbnail((1200, 1200))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True)
    key = f"dishes/{a.restaurant.id}/{public_token(12)}.jpg"
    get_storage().save(key, out.getvalue())
    hue = (it.image or {}).get("hue", 30)
    it.image = {"kind": "photo", "hue": hue, "url": f"/api/v1/media/{key}", "provenance": "Photo uploaded by the restaurant"}
    audit(db, a.actor, "item.image_uploaded", a.restaurant.id, "item", it.id)
    db.commit()
    return {"image": it.image}


@router.delete("/restaurants/{restaurant_id}/items/{item_id}/image")
def remove_item_image(item_id: str, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    it = _item_for(db, a, item_id)
    hue = (it.image or {}).get("hue", 30)
    it.image = {"kind": "plate", "hue": hue, "provenance": "Sample illustration generated for demo — replace with your own photo"}
    audit(db, a.actor, "item.image_removed", a.restaurant.id, "item", it.id)
    db.commit()
    return {"image": it.image}


@router.post("/restaurants/{restaurant_id}/menus/{menu_id}/items", status_code=201)
def add_item(menu_id: str, body: ItemIn, a: Access = Depends(require("menu.edit")), db: Session = Depends(get_db)):
    m = _menu_for(db, a, menu_id)
    cat = db.get(Category, body.category_id)
    if not cat or cat.menu_id != m.id:
        raise DomainError("bad_category", "Pick a category from this menu.", 422)
    it = Item(menu_id=m.id, category_id=cat.id, name=body.name, description=body.description, price_minor=body.price_minor, currency=a.restaurant.currency, state=body.state, stock_remaining=body.stock_remaining, sort=len(cat.items),
              attributes=[x.model_dump() for x in body.attributes], allergens=body.allergens.model_dump(), ingredients=body.ingredients.model_dump(), image=body.image.model_dump(), modifier_groups=[g.model_dump() for g in body.modifier_groups])
    db.add(it)
    audit(db, a.actor, "item.created", a.restaurant.id, "item", it.id, {"name": it.name, "price": it.price_minor})
    db.commit()
    return {"id": it.id, "key": it.stable_key}


@router.patch("/restaurants/{restaurant_id}/items/{item_id}")
def patch_item(item_id: str, body: ItemPatch, a: Access = Depends(require("menu.view")), db: Session = Depends(get_db)):
    it = _item_for(db, a, item_id)
    data = body.model_dump(exclude_unset=True)
    ops_only = set(data) <= {"state", "stock_remaining", "clear_stock"}
    if not has_perm(a.role, "menu.edit") and not (ops_only and has_perm(a.role, "menu.availability")):
        raise DomainError("forbidden", "Your role can only change availability.", 403)
    changes = {}
    for f in ("name", "description", "price_minor", "state", "sort", "archived"):
        if f in data and data[f] is not None and getattr(it, f) != data[f]:
            changes[f] = [getattr(it, f), data[f]]
            setattr(it, f, data[f])
    if "category_id" in data and data["category_id"]:
        c = db.get(Category, data["category_id"])
        if not c or c.menu_id != it.menu_id:
            raise DomainError("bad_category", "Pick a category from this menu.", 422)
        it.category_id = c.id
    if data.get("clear_stock"):
        it.stock_remaining = None
        changes["stock"] = "cleared"
    elif "stock_remaining" in data and data["stock_remaining"] is not None:
        changes["stock"] = [it.stock_remaining, data["stock_remaining"]]
        it.stock_remaining = data["stock_remaining"]
    for f, val in (("attributes", [x.model_dump() for x in body.attributes] if body.attributes is not None else None), ("allergens", body.allergens.model_dump() if body.allergens else None), ("ingredients", body.ingredients.model_dump() if body.ingredients else None), ("image", body.image.model_dump() if body.image else None), ("modifier_groups", [g.model_dump() for g in body.modifier_groups] if body.modifier_groups is not None else None)):
        if val is not None:
            setattr(it, f, val)
            changes[f] = "updated"
    audit(db, a.actor, "item.updated", a.restaurant.id, "item", it.id, changes)
    db.commit()
    return {"id": it.id}


@router.post("/restaurants/{restaurant_id}/items/bulk")
def bulk_items(body: BulkItems, a: Access = Depends(require("menu.view")), db: Session = Depends(get_db)):
    if not has_perm(a.role, "menu.edit") and not (body.archived is None and has_perm(a.role, "menu.availability")):
        raise DomainError("forbidden", "Your role can only change availability.", 403)
    n = 0
    for iid in body.item_ids:
        it = _item_for(db, a, iid)
        if body.state:
            it.state = body.state
        if body.archived is not None:
            it.archived = body.archived
        n += 1
    audit(db, a.actor, "item.bulk_updated", a.restaurant.id, "item", "", {"count": n, "state": body.state, "archived": body.archived})
    db.commit()
    return {"updated": n}


# ───────── availability + recommendation rules ─────────
def _rule_out(r):
    return {c.name: _iso(getattr(r, c.name)) if isinstance(getattr(r, c.name), datetime) else getattr(r, c.name) for c in r.__table__.columns}


@router.get("/restaurants/{restaurant_id}/availability-rules")
def list_rules(a: Access = Depends(require("menu.view")), db: Session = Depends(get_db)):
    return [_rule_out(r) for r in db.query(AvailabilityRule).filter(AvailabilityRule.restaurant_id == a.restaurant.id).order_by(AvailabilityRule.created_at).all()]


@router.post("/restaurants/{restaurant_id}/availability-rules", status_code=201)
def add_rule(body: AvailabilityRuleIn, a: Access = Depends(require("availability.edit")), db: Session = Depends(get_db)):
    if body.target_type != "restaurant" and not body.target_id:
        raise DomainError("target_required", "Choose what this schedule applies to.", 422)
    if body.kind == "date_exception" and not body.start_date:
        raise DomainError("date_required", "Pick a date for the exception.", 422)
    if bool(body.start_time) != bool(body.end_time):
        raise DomainError("window_incomplete", "Set both a start and an end time.", 422)
    r = AvailabilityRule(restaurant_id=a.restaurant.id, **body.model_dump())
    if r.target_type == "restaurant":
        r.target_id = None
    db.add(r)
    audit(db, a.actor, "availability.created", a.restaurant.id, "availability_rule", r.id, body.model_dump())
    db.commit()
    return _rule_out(r)


@router.patch("/restaurants/{restaurant_id}/availability-rules/{rule_id}")
def patch_rule(rule_id: str, body: AvailabilityRulePatch, a: Access = Depends(require("availability.edit")), db: Session = Depends(get_db)):
    r = db.get(AvailabilityRule, rule_id)
    if not r or r.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Schedule not found.", 404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    audit(db, a.actor, "availability.updated", a.restaurant.id, "availability_rule", r.id, body.model_dump(exclude_unset=True))
    db.commit()
    return _rule_out(r)


@router.delete("/restaurants/{restaurant_id}/availability-rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, a: Access = Depends(require("availability.edit")), db: Session = Depends(get_db)):
    r = db.get(AvailabilityRule, rule_id)
    if not r or r.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Schedule not found.", 404)
    db.delete(r)
    audit(db, a.actor, "availability.deleted", a.restaurant.id, "availability_rule", rule_id)
    db.commit()


@router.get("/restaurants/{restaurant_id}/recommendation-rules")
def list_rec_rules(a: Access = Depends(require("menu.view")), db: Session = Depends(get_db)):
    return [_rule_out(r) for r in db.query(RecommendationRule).filter(RecommendationRule.restaurant_id == a.restaurant.id).all()]


@router.post("/restaurants/{restaurant_id}/recommendation-rules", status_code=201)
def add_rec_rule(body: RecommendationRuleIn, a: Access = Depends(require("recommendations.edit")), db: Session = Depends(get_db)):
    r = RecommendationRule(restaurant_id=a.restaurant.id, **body.model_dump())
    db.add(r)
    audit(db, a.actor, "recommendation.created", a.restaurant.id, "recommendation_rule", r.id, {"target": body.target_id, "weight": body.weight})
    db.commit()
    return _rule_out(r)


@router.patch("/restaurants/{restaurant_id}/recommendation-rules/{rule_id}")
def patch_rec_rule(rule_id: str, body: RecommendationRulePatch, a: Access = Depends(require("recommendations.edit")), db: Session = Depends(get_db)):
    r = db.get(RecommendationRule, rule_id)
    if not r or r.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Promotion not found.", 404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    audit(db, a.actor, "recommendation.updated", a.restaurant.id, "recommendation_rule", r.id, body.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    return _rule_out(r)


@router.delete("/restaurants/{restaurant_id}/recommendation-rules/{rule_id}", status_code=204)
def delete_rec_rule(rule_id: str, a: Access = Depends(require("recommendations.edit")), db: Session = Depends(get_db)):
    r = db.get(RecommendationRule, rule_id)
    if not r or r.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Promotion not found.", 404)
    db.delete(r)
    audit(db, a.actor, "recommendation.deleted", a.restaurant.id, "recommendation_rule", rule_id)
    db.commit()


# ───────── tables + QR ─────────
def _qr_url(token: str) -> str:
    return f"{get_settings().public_base_url}/t/{token}"


@router.get("/restaurants/{restaurant_id}/tables")
def list_tables(a: Access = Depends(require("tables.view")), db: Session = Depends(get_db)):
    out = []
    for t in db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == a.restaurant.id).all():
        qr = db.query(QrCode).filter(QrCode.table_id == t.id, QrCode.active.is_(True)).first()
        live = db.query(TableSession).filter(TableSession.table_id == t.id, TableSession.state.in_(sess.LIVE_STATES)).first()
        out.append({"id": t.id, "label": t.label, "zone": t.zone, "status": t.status, "qr_id": qr.id if qr else None, "qr_token": qr.token if qr else None, "qr_url": _qr_url(qr.token) if qr else None, "session_state": live.state if live else None})
    return sorted(out, key=lambda x: (len(x["label"]), x["label"]))


@router.post("/restaurants/{restaurant_id}/tables", status_code=201)
def add_table(body: TableIn, a: Access = Depends(require("tables.manage")), db: Session = Depends(get_db)):
    if db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == a.restaurant.id, RestaurantTable.label == body.label).first():
        raise DomainError("table_exists", "A table with that name already exists.", 409)
    t = RestaurantTable(restaurant_id=a.restaurant.id, label=body.label, zone=body.zone)
    db.add(t)
    db.flush()
    qr = QrCode(restaurant_id=a.restaurant.id, table_id=t.id, token=public_token(16))
    db.add(qr)
    audit(db, a.actor, "table.created", a.restaurant.id, "table", t.id, {"label": t.label})
    db.commit()
    return {"id": t.id, "qr_url": _qr_url(qr.token)}


@router.post("/restaurants/{restaurant_id}/tables/{table_id}/qr-codes", status_code=201)
def rotate_qr(table_id: str, a: Access = Depends(require("tables.manage")), db: Session = Depends(get_db)):
    t = db.get(RestaurantTable, table_id)
    if not t or t.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Table not found.", 404)
    db.query(QrCode).filter(QrCode.table_id == t.id).update({"active": False})
    qr = QrCode(restaurant_id=a.restaurant.id, table_id=t.id, token=public_token(16))
    db.add(qr)
    audit(db, a.actor, "qr.rotated", a.restaurant.id, "table", t.id)
    db.commit()
    return {"qr_url": _qr_url(qr.token)}


@router.get("/restaurants/{restaurant_id}/qr-codes/{qr_id}/image.svg")
def qr_image(qr_id: str, a: Access = Depends(require("tables.view")), db: Session = Depends(get_db)):
    qr = db.get(QrCode, qr_id)
    if not qr or qr.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "QR code not found.", 404)
    buf = io.BytesIO()
    segno.make(_qr_url(qr.token), error="m").save(buf, kind="svg", scale=8, border=2, dark="#111111")
    return Response(buf.getvalue(), media_type="image/svg+xml")


# ───────── orders, sessions, kitchen ─────────
def _orders_query(db, rid):
    return db.query(Order).filter(Order.restaurant_id == rid)


@router.get("/restaurants/{restaurant_id}/orders")
def list_orders(state: str | None = None, limit: int = 100, a: Access = Depends(require("orders.view")), db: Session = Depends(get_db)):
    q = _orders_query(db, a.restaurant.id)
    if state:
        q = q.filter(Order.state.in_(state.split(",")))
    return [order_service.serialize_order(o) for o in q.order_by(Order.created_at.desc()).limit(min(limit, 300)).all()]


@router.get("/restaurants/{restaurant_id}/kitchen/queue")
def kitchen_queue(a: Access = Depends(require("kitchen.view")), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    rows = _orders_query(db, a.restaurant.id).filter((Order.state.in_(list(order_service.ACTIVE_STATES))) | ((Order.state == "served") & (Order.created_at >= since))).order_by(Order.created_at).all()
    out = []
    for o in rows:
        v = order_service.serialize_order(o)
        first = next((x for x in o.session.orders if x.ticket_seq == 1), None)
        v["follows_number"] = first.number if o.ticket_type == "addon" and first else None
        out.append(v)
    cursor = db.query(func.max(OrderStatusEvent.seq)).filter(OrderStatusEvent.restaurant_id == a.restaurant.id).scalar() or 0
    return {"tickets": out, "cursor": cursor, "can_cancel": has_perm(a.role, "orders.cancel")}


@router.get("/restaurants/{restaurant_id}/kitchen/events")
def kitchen_events(since: int = 0, a: Access = Depends(require("kitchen.view")), db: Session = Depends(get_db)):
    evs = db.query(OrderStatusEvent).filter(OrderStatusEvent.restaurant_id == a.restaurant.id, OrderStatusEvent.seq > since).order_by(OrderStatusEvent.seq).limit(200).all()
    return {"events": [{"seq": e.seq, "order_id": e.order_id, "to": e.to_state, "at": e.at.isoformat()} for e in evs], "cursor": evs[-1].seq if evs else since}


def _order_access(db, user, order_id, perm):
    o = db.get(Order, order_id)
    if not o:
        raise DomainError("not_found", "Order not found.", 404)
    return o, access_for(db, user, o.restaurant_id, perm)


@router.post("/orders/{order_id}/status-transition")
def status_transition(order_id: str, body: TransitionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o, a = _order_access(db, user, order_id, "orders.transition")
    o = order_service.transition(db, o.id, body.to_state, a.actor, can_cancel=has_perm(a.role, "orders.cancel"), reason=body.reason)
    return order_service.serialize_order(o)


@router.post("/orders/{order_id}/acknowledge")
def acknowledge(order_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o, a = _order_access(db, user, order_id, "orders.transition")
    o = order_service.transition(db, o.id, "accepted", a.actor, can_cancel=False)
    return order_service.serialize_order(o)


@router.post("/orders/{order_id}/pos-sync")
def pos_sync(order_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o, a = _order_access(db, user, order_id, "pos.sync")
    ev = db.query(IntegrationEvent).filter(IntegrationEvent.order_id == o.id).first()
    if not ev:
        ev = IntegrationEvent(restaurant_id=o.restaurant_id, order_id=o.id, provider="mock-pos", simulated=True)
        db.add(ev)
    ev.attempts += 1
    ev.status, ev.external_ref = "synced", f"SIM-{o.number}"
    audit(db, a.actor, "pos.sync_simulated", o.restaurant_id, "order", o.id)
    db.commit()
    return {"status": ev.status, "simulated": True, "external_ref": ev.external_ref}


@router.get("/restaurants/{restaurant_id}/sessions")
def list_sessions(state: str | None = None, a: Access = Depends(require("sessions.view")), db: Session = Depends(get_db)):
    q = db.query(TableSession).filter(TableSession.restaurant_id == a.restaurant.id)
    q = q.filter(TableSession.state.in_(state.split(","))) if state else q.filter(TableSession.state.in_(list(sess.LIVE_STATES) + ["paid"]))
    out = []
    for s in q.order_by(TableSession.opened_at.desc()).limit(100).all():
        bill = compute_bill(a.restaurant, s.orders)
        out.append({"id": s.id, "table": s.table.label, "zone": s.table.zone, "state": s.state, "opened_at": _iso(s.opened_at), "guest": s.contact_name, "phone_masked": mask(s.contact_phone) if s.contact_phone else None, "tickets": len(s.orders), "total_minor": bill["total_minor"], "item_count": bill["item_count"]})
    return out


@router.post("/restaurants/{restaurant_id}/sessions/{session_id}/action")
def session_action(session_id: str, body: dict, a: Access = Depends(require("sessions.manage")), db: Session = Depends(get_db)):
    s = db.get(TableSession, session_id)
    if not s or s.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Table session not found.", 404)
    act = body.get("action")
    if act == "release_lock":
        sess.release_payment_lock(db, s.id, a.actor)
    elif act == "close":
        sess.close_session(db, s.id, a.actor)
    elif act == "reopen":
        sess.reopen_session(db, s.id, a.actor)
    elif act == "transfer":
        sess.transfer_session(db, s.id, str(body.get("to_table_id", "")), a.actor)
    elif act == "force_close":
        sess.close_session(db, s.id, a.actor, force=True, reason=str(body.get("reason", ""))[:200])
    else:
        raise DomainError("bad_action", "Unknown action.", 422)
    db.refresh(s)
    return {"id": s.id, "state": s.state}


# ───────── payments, receipts, notifications ─────────
@router.get("/restaurants/{restaurant_id}/payments")
def list_payments(a: Access = Depends(require("payments.view")), db: Session = Depends(get_db)):
    out = []
    for p in db.query(Payment).filter(Payment.restaurant_id == a.restaurant.id).order_by(Payment.created_at.desc()).limit(100).all():
        s = db.get(TableSession, p.session_id)
        rc = db.query(Receipt).filter(Receipt.payment_id == p.id).first()
        evs = db.query(PaymentEvent).filter(PaymentEvent.payment_id == p.id).order_by(PaymentEvent.created_at).all()
        out.append({"id": p.id, "table": s.table.label, "provider": p.provider, "provider_ref": p.provider_ref, "state": p.state, "amount_minor": p.amount_minor, "currency": p.currency, "simulated": p.simulated, "failure_reason": p.failure_reason, "refunded_minor": p.refunded_minor, "refund_reason": p.refund_reason, "refund_ref": p.refund_ref, "created_at": _iso(p.created_at), "paid_at": _iso(p.paid_at),
                    "receipt": {"id": rc.id, "number": rc.number, "token": rc.token, "revoked": rc.revoked} if rc else None,
                    "events": [{"event_id": e.event_id, "type": e.event_type, "outcome": e.outcome, "verified": e.verified, "at": _iso(e.created_at)} for e in evs]})
    return out


@router.post("/restaurants/{restaurant_id}/payments/{payment_id}/refund")
def refund(payment_id: str, body: RefundIn, a: Access = Depends(require("payments.refund")), db: Session = Depends(get_db)):
    p = sess.refund_payment(db, payment_id, a.restaurant.id, a.actor, body.reason)
    return {"id": p.id, "state": p.state, "refunded_minor": p.refunded_minor, "simulated": p.simulated}


@router.get("/restaurants/{restaurant_id}/reviews")
def list_reviews(a: Access = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    rows = db.query(Review).filter(Review.restaurant_id == a.restaurant.id).order_by(Review.created_at.desc()).limit(100).all()
    avg = db.query(func.avg(Review.rating)).filter(Review.restaurant_id == a.restaurant.id).scalar()
    dist = dict(db.query(Review.rating, func.count()).filter(Review.restaurant_id == a.restaurant.id).group_by(Review.rating).all())
    return {"average": round(float(avg), 2) if avg else None, "count": len(rows), "distribution": {str(n): dist.get(n, 0) for n in range(1, 6)},
            "reviews": [{"id": r.id, "rating": r.rating, "comment": r.comment, "guest": r.guest_first_name, "simulated": r.simulated, "created_at": _iso(r.created_at)} for r in rows]}


@router.post("/restaurants/{restaurant_id}/receipts/{receipt_id}/revoke")
def revoke_receipt(receipt_id: str, a: Access = Depends(require("payments.view")), db: Session = Depends(get_db)):
    if not has_perm(a.role, "settings.edit"):
        raise DomainError("forbidden", "Only owners can revoke receipt links.", 403)
    rc = db.get(Receipt, receipt_id)
    if not rc or rc.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Receipt not found.", 404)
    rc.revoked = True
    audit(db, a.actor, "receipt.revoked", a.restaurant.id, "receipt", rc.id)
    db.commit()
    return {"revoked": True}


@router.get("/restaurants/{restaurant_id}/notifications")
def list_notifications(a: Access = Depends(require("payments.view")), db: Session = Depends(get_db)):
    jobs = db.query(NotificationJob).filter(NotificationJob.restaurant_id == a.restaurant.id).order_by(NotificationJob.created_at.desc()).limit(100).all()
    out = []
    for j in jobs:
        rc = db.get(Receipt, j.receipt_id)
        out.append({"id": j.id, "channel": j.channel, "recipient": mask(j.recipient), "state": j.state, "attempts": j.attempts, "simulated": j.simulated, "provider": j.provider, "last_error": j.last_error, "receipt_number": rc.number if rc else None, "next_attempt_at": _iso(j.next_attempt_at), "sent_at": _iso(j.sent_at)})
    return out


@router.post("/notifications/{notification_id}/retry")
def retry_notification(notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(NotificationJob, notification_id)
    if not j:
        raise DomainError("not_found", "Notification not found.", 404)
    a = access_for(db, user, j.restaurant_id, "notifications.retry")
    if j.state == "sent":
        raise DomainError("already_sent", "This notification was already sent.", 409)
    j.attempts = 0
    audit(db, a.actor, "notification.retry", j.restaurant_id, "notification", j.id)
    deliver(db, j)
    return {"state": j.state, "last_error": j.last_error}


# ───────── uploads / ingestion ─────────
def _job_view(j: IngestionJob):
    return {"id": j.id, "status": j.status, "method": j.method, "attempts": j.attempts, "error": j.error, "filename": j.upload.filename, "content_type": j.upload.content_type, "size_bytes": j.upload.size_bytes, "created_at": _iso(j.created_at), "finished_at": _iso(j.finished_at), "draft_menu_id": j.draft_menu_id}


def _run_job(job_id: str):
    db = SessionLocal()
    try:
        ing.process_job(db, job_id)
    finally:
        db.close()


@router.post("/restaurants/{restaurant_id}/menu-uploads", status_code=201)
async def upload_menu(bg: BackgroundTasks, file: UploadFile = File(...), a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    up = ing.save_upload(db, a.restaurant.id, file.filename or "menu", data, a.user.id, a.actor)
    job = db.query(IngestionJob).filter(IngestionJob.upload_id == up.id).one()
    bg.add_task(_run_job, job.id)
    return _job_view(job)


@router.get("/restaurants/{restaurant_id}/ingestion-jobs")
def list_jobs(a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    return [_job_view(j) for j in db.query(IngestionJob).filter(IngestionJob.restaurant_id == a.restaurant.id).order_by(IngestionJob.created_at.desc()).limit(50).all()]


def _job_for(db, a, job_id):
    j = db.get(IngestionJob, job_id)
    if not j or j.restaurant_id != a.restaurant.id:
        raise DomainError("not_found", "Import not found.", 404)
    return j


@router.post("/restaurants/{restaurant_id}/ingestion-jobs/{job_id}/process")
def retry_job(job_id: str, a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    j = _job_for(db, a, job_id)
    if j.status in ("processing", "approved"):
        raise DomainError("not_retryable", "This import can't be retried now.", 409)
    return _job_view(ing.process_job(db, j.id))


@router.get("/restaurants/{restaurant_id}/ingestion-jobs/{job_id}/candidates")
def candidates(job_id: str, a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    j = _job_for(db, a, job_id)
    cs = db.query(IngestionCandidate).filter(IngestionCandidate.job_id == j.id).order_by(IngestionCandidate.sort).all()
    return {"job": _job_view(j), "candidates": [{"id": c.id, "category": c.category, "name": c.name, "description": c.description, "price_minor": c.price_minor, "confidence": c.confidence, "flags": c.flags, "source": c.source, "review_state": c.review_state, "edited": c.edited} for c in cs]}


@router.patch("/restaurants/{restaurant_id}/ingestion-candidates/{candidate_id}")
def patch_candidate(candidate_id: str, body: CandidatePatch, a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    c = db.get(IngestionCandidate, candidate_id)
    if not c:
        raise DomainError("not_found", "Dish not found.", 404)
    _job_for(db, a, c.job_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
        if k != "review_state":
            c.edited = True
    if c.price_minor is not None and "price_missing" in c.flags:
        c.flags = [f for f in c.flags if f != "price_missing"]
    db.commit()
    return {"id": c.id}


@router.post("/restaurants/{restaurant_id}/ingestion-jobs/{job_id}/bulk")
def bulk_candidates(job_id: str, body: dict, a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    j = _job_for(db, a, job_id)
    state = body.get("review_state")
    if state not in ("approved", "rejected", "pending"):
        raise DomainError("bad_state", "Unknown review state.", 422)
    q = db.query(IngestionCandidate).filter(IngestionCandidate.job_id == j.id)
    if body.get("ids"):
        q = q.filter(IngestionCandidate.id.in_(body["ids"]))
    if body.get("only_unflagged"):
        n = 0
        for c in q.all():
            if not c.flags:
                c.review_state, n = state, n + 1
    else:
        n = q.update({"review_state": state}, synchronize_session=False)
    db.commit()
    return {"updated": n}


@router.post("/restaurants/{restaurant_id}/ingestion-jobs/{job_id}/approve")
def approve(job_id: str, a: Access = Depends(require("uploads.manage")), db: Session = Depends(get_db)):
    d = ing.approve_job(db, _job_for(db, a, job_id), a.actor)
    return {"draft_menu_id": d.id, "version": d.version}


# ───────── dashboard, analytics, audit, staff ─────────
@router.get("/restaurants/{restaurant_id}/dashboard")
def dashboard(a: Access = Depends(require("orders.view")), db: Session = Depends(get_db)):
    rid = a.restaurant.id
    day = datetime.now(timezone.utc) - timedelta(hours=24)
    paid = db.query(func.coalesce(func.sum(Payment.amount_minor), 0)).filter(Payment.restaurant_id == rid, Payment.state == "succeeded", Payment.paid_at >= day).scalar()
    return {
        "orders_24h": _orders_query(db, rid).filter(Order.created_at >= day).count(),
        "active_tickets": _orders_query(db, rid).filter(Order.state.in_(list(order_service.ACTIVE_STATES))).count(),
        "active_tables": db.query(TableSession).filter(TableSession.restaurant_id == rid, TableSession.state.in_(sess.LIVE_STATES)).count(),
        "awaiting_payment": db.query(TableSession).filter(TableSession.restaurant_id == rid, TableSession.state.in_(["bill_requested", "payment_pending"])).count(),
        "paid_24h_minor": int(paid), "currency": a.restaurant.currency,
        "imports_to_review": db.query(IngestionJob).filter(IngestionJob.restaurant_id == rid, IngestionJob.status == "review").count(),
        "failed_notifications": db.query(NotificationJob).filter(NotificationJob.restaurant_id == rid, NotificationJob.state == "failed").count(),
        "sold_out_items": db.query(Item).join(Menu).filter(Menu.restaurant_id == rid, Menu.status == "published", Item.archived.is_(False), (Item.state == "sold_out") | (Item.stock_remaining == 0)).count(),
    }


@router.get("/restaurants/{restaurant_id}/analytics")
def analytics(a: Access = Depends(require("analytics.view")), db: Session = Depends(get_db)):
    rid = a.restaurant.id
    since = datetime.now(timezone.utc) - timedelta(days=14)
    orders = _orders_query(db, rid).filter(Order.created_at >= since, Order.state.notin_(["rejected", "cancelled"])).all()
    tz = ZoneInfo(a.restaurant.timezone)
    by_day: dict[str, int] = {}
    by_hour = [0] * 24
    for o in orders:
        c = o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=timezone.utc)
        loc = c.astimezone(tz)
        by_day[loc.strftime("%Y-%m-%d")] = by_day.get(loc.strftime("%Y-%m-%d"), 0) + 1
        by_hour[loc.hour] += 1
    top = (db.query(OrderItem.name_snapshot, func.sum(OrderItem.quantity).label("q")).join(Order).filter(Order.restaurant_id == rid, Order.created_at >= since, Order.state.notin_(["rejected", "cancelled"])).group_by(OrderItem.name_snapshot).order_by(func.sum(OrderItem.quantity).desc()).limit(8).all())
    ev = dict(db.query(AnalyticsEvent.event_type, func.count()).filter(AnalyticsEvent.restaurant_id == rid, AnalyticsEvent.at >= since).group_by(AnalyticsEvent.event_type).all())
    demo = db.query(AnalyticsEvent).filter(AnalyticsEvent.restaurant_id == rid, AnalyticsEvent.is_demo.is_(True)).count() > 0 or a.restaurant.is_demo
    days = [(datetime.now(tz) - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(13, -1, -1)]
    return {"includes_demo_data": demo, "orders_by_day": [{"day": d, "orders": by_day.get(d, 0)} for d in days], "orders_by_hour": [{"hour": h, "orders": n} for h, n in enumerate(by_hour)], "top_items": [{"name": n, "quantity": int(q)} for n, q in top], "engagement": ev}


@router.get("/restaurants/{restaurant_id}/audit")
def audit_log(a: Access = Depends(require("settings.view")), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).filter(AuditLog.restaurant_id == a.restaurant.id).order_by(AuditLog.at.desc()).limit(150).all()
    return [{"actor": r.actor, "action": r.action, "resource": r.resource_type, "detail": r.detail, "at": _iso(r.at)} for r in rows]


@router.get("/restaurants/{restaurant_id}/staff")
def list_staff(a: Access = Depends(require("staff.view")), db: Session = Depends(get_db)):
    return [{"id": m.id, "email": m.user.email, "name": m.user.name, "role": m.role} for m in db.query(Membership).filter(Membership.restaurant_id == a.restaurant.id).all()]


@router.post("/restaurants/{restaurant_id}/staff", status_code=201)
def add_staff(body: StaffIn, a: Access = Depends(require("staff.manage")), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == body.email.lower()).first()
    if not u:
        if not body.password:
            raise DomainError("password_required", "Set a starting password for the new user.", 422)
        u = User(email=body.email.lower(), name=body.name, password_hash=hash_password(body.password))
        db.add(u)
        db.flush()
    if db.query(Membership).filter(Membership.user_id == u.id, Membership.restaurant_id == a.restaurant.id).first():
        raise DomainError("already_member", "That person already has access.", 409)
    db.add(Membership(user_id=u.id, restaurant_id=a.restaurant.id, role=body.role))
    audit(db, a.actor, "staff.added", a.restaurant.id, "user", u.id, {"role": body.role})
    db.commit()
    return {"id": u.id}


@router.delete("/restaurants/{restaurant_id}/staff/{membership_id}", status_code=204)
def remove_staff(membership_id: str, a: Access = Depends(require("staff.manage")), db: Session = Depends(get_db)):
    m = db.get(Membership, membership_id)
    if not m or m.restaurant_id != a.restaurant.id or m.role == "owner":
        raise DomainError("not_found", "Staff member not found.", 404)
    db.delete(m)
    audit(db, a.actor, "staff.removed", a.restaurant.id, "membership", membership_id)
    db.commit()


# ───────── platform ─────────
@router.get("/platform/restaurants")
def platform_restaurants(admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    return [{"id": r.id, "slug": r.slug, "name": r.name, "status": r.status, "is_demo": r.is_demo} for r in db.query(Restaurant).all()]


@router.get("/platform/health")
def platform_health(admin: User = Depends(platform_admin), db: Session = Depends(get_db)):
    return {"failed_ingestion_jobs": db.query(IngestionJob).filter(IngestionJob.status == "failed").count(), "failed_notifications": db.query(NotificationJob).filter(NotificationJob.state == "failed").count(),
            "rejected_webhooks": db.query(AuditLog).filter(AuditLog.action == "payment.webhook_rejected").count(), "payment_provider": get_settings().payment_provider, "demo_mode": get_settings().demo_mode}
