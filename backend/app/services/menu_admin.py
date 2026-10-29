"""Menu versioning: clone-to-draft and publish. Published data is untouched until publish."""
from __future__ import annotations

import copy
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from ..models import Category, Item, Menu
from .audit import audit
from .errors import DomainError


def published_or_none(db: Session, restaurant_id: str) -> Menu | None:
    return db.query(Menu).options(selectinload(Menu.categories).selectinload(Category.items)).filter(Menu.restaurant_id == restaurant_id, Menu.status == "published").order_by(Menu.version.desc()).first()


def clone_menu(db: Session, src: Menu, restaurant_id: str, name: str | None = None) -> Menu:
    version = (db.query(func.max(Menu.version)).filter(Menu.restaurant_id == restaurant_id).scalar() or 0) + 1
    new = Menu(restaurant_id=restaurant_id, name=name or src.name, version=version, status="draft")
    db.add(new)
    db.flush()
    for c in src.categories:
        nc = Category(menu_id=new.id, stable_key=c.stable_key, name=c.name, description=c.description, sort=c.sort)
        db.add(nc)
        db.flush()
        for it in c.items:
            db.add(Item(menu_id=new.id, category_id=nc.id, stable_key=it.stable_key, name=it.name, description=it.description, price_minor=it.price_minor, currency=it.currency, state=it.state, archived=it.archived, sort=it.sort, stock_remaining=it.stock_remaining, attributes=copy.deepcopy(it.attributes), allergens=copy.deepcopy(it.allergens), ingredients=copy.deepcopy(it.ingredients), image=copy.deepcopy(it.image), modifier_groups=copy.deepcopy(it.modifier_groups)))
    db.flush()
    return new


def publish_menu(db: Session, menu: Menu, actor: str) -> Menu:
    if menu.status == "published":
        raise DomainError("already_published", "This menu is already live.", 409)
    if menu.status == "archived":
        raise DomainError("archived", "Archived menus can't be published. Clone it to a new draft first.", 409)
    if not any(not i.archived for c in menu.categories for i in c.items):
        raise DomainError("empty_menu", "Add at least one dish before publishing.", 422)
    for old in db.query(Menu).filter(Menu.restaurant_id == menu.restaurant_id, Menu.status == "published").all():
        old.status = "archived"
    menu.status, menu.published_at = "published", datetime.now(timezone.utc)
    audit(db, actor, "menu.published", menu.restaurant_id, "menu", menu.id, {"version": menu.version})
    db.commit()
    return menu
