"""Menu loading + serialization shared by public and admin routes."""
from datetime import datetime

from sqlalchemy.orm import Session, joinedload, selectinload

from ..defaults import merged_config, merged_theme
from ..models import AvailabilityRule, Category, Menu, RecommendationRule, Restaurant
from .availability import Availability, RulesIndex, evaluate_item, restaurant_is_open


def published_menu(db: Session, restaurant_id: str) -> Menu | None:
    return (
        db.query(Menu)
        .options(selectinload(Menu.categories).selectinload(Category.items))
        .filter(Menu.restaurant_id == restaurant_id, Menu.status == "published")
        .order_by(Menu.version.desc())
        .first()
    )


def rules_index(db: Session, restaurant_id: str) -> RulesIndex:
    return RulesIndex.build(db.query(AvailabilityRule).filter(AvailabilityRule.restaurant_id == restaurant_id).all())


def active_recommendation_rules(db: Session, restaurant_id: str, now: datetime) -> list[RecommendationRule]:
    out = []
    for r in db.query(RecommendationRule).filter(RecommendationRule.restaurant_id == restaurant_id, RecommendationRule.active.is_(True)).all():
        s = r.start_at if r.start_at is None or r.start_at.tzinfo else r.start_at.replace(tzinfo=now.tzinfo)
        e = r.end_at if r.end_at is None or r.end_at.tzinfo else r.end_at.replace(tzinfo=now.tzinfo)
        if (s and now < s) or (e and now >= e):
            continue
        out.append(r)
    return out


def public_restaurant(r: Restaurant, idx: RulesIndex, now: datetime) -> dict:
    cfg = merged_config(r.config)
    return {
        "id": r.id,
        "slug": r.slug,
        "name": r.name,
        "tagline": r.tagline,
        "venue_type": r.venue_type,
        "cuisine": r.cuisine,
        "timezone": r.timezone,
        "currency": r.currency,
        "locale": r.locale,
        "is_demo": r.is_demo,
        "theme": merged_theme(r.theme),
        "features": cfg["features"],
        "card_density": cfg["card_density"],
        "tax": {"label": cfg["tax"]["label"], "bps": cfg["tax"]["gst_bps"], "inclusive": cfg["tax"]["inclusive"]},
        "service_charge_bps": cfg["service_charge_bps"],
        "contact_required": cfg["ordering"]["contact_required"],
        "status": restaurant_is_open(r, idx, now),
    }


def serialize_item(item, availability: Availability, tag_labels: dict | None = None, promo: dict | None = None) -> dict:
    return {
        "id": item.id,
        "key": item.stable_key,
        "category_id": item.category_id,
        "name": item.name,
        "description": item.description,
        "price_minor": item.price_minor,
        "currency": item.currency,
        "attributes": item.attributes,
        "allergens": item.allergens,
        "ingredients": item.ingredients,
        "image": item.image,
        "modifier_groups": item.modifier_groups,
        "availability": availability.as_dict(),
        "stock_remaining": item.stock_remaining if item.stock_remaining is not None and item.stock_remaining <= 5 else None,
        "promo": promo,
    }


def build_public_menu(db: Session, restaurant: Restaurant, now: datetime) -> dict:
    menu = published_menu(db, restaurant.id)
    idx = rules_index(db, restaurant.id)
    promos = promo_labels(db, restaurant.id, now)
    cats = []
    if menu:
        for c in menu.categories:
            items = []
            for it in c.items:
                av = evaluate_item(it, c, restaurant, idx, now)
                if av.status == "hidden":
                    continue
                items.append(serialize_item(it, av, promo=promos.get(it.stable_key)))
            if items:
                cat_av = evaluate_category(c, restaurant, idx, now)
                cats.append({"id": c.id, "name": c.name, "description": c.description, "note": cat_av, "items": items})
    return {"menu_id": menu.id if menu else None, "version": menu.version if menu else None, "categories": cats}


def evaluate_category(c, restaurant, idx: RulesIndex, now) -> str | None:
    rules = idx.for_level("category", c.stable_key)
    if not rules:
        return None
    from .availability import _time_open
    from zoneinfo import ZoneInfo

    ok, _, _ = _time_open([("category", rules)], now.astimezone(ZoneInfo(restaurant.timezone)))
    if ok:
        return None
    return "Served at set times"


def promo_labels(db: Session, restaurant_id: str, now: datetime) -> dict:
    """Item stable_key -> {label, featured}. Labels are admin-authored promotions, never 'popular' claims."""
    menu = published_menu(db, restaurant_id)
    out: dict = {}
    if not menu:
        return out
    cat_by_key = {c.stable_key: c for c in menu.categories}
    for r in active_recommendation_rules(db, restaurant_id, now):
        if not (r.featured or r.label):
            continue
        info = {"label": r.label or "Featured", "featured": r.featured}
        if r.target_type == "item":
            out[r.target_id] = info
        elif r.target_type == "category" and r.target_id in cat_by_key:
            for it in cat_by_key[r.target_id].items:
                out.setdefault(it.stable_key, info)
    return out


def find_item(menu: Menu, item_id: str):
    for c in menu.categories:
        for it in c.items:
            if it.id == item_id:
                return it, c
    return None, None
