"""Demo data. Every restaurant here is SAMPLE content (is_demo=True) — no real venues, reviews or
popularity claims. Run: python -m app.seed [--reset]"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from .db import Base, SessionLocal, engine
from .defaults import DEFAULT_CONFIG, merged_config
from .models import *  # noqa
from .providers.payments import get_provider
from .security import hash_password, public_token
from .services import sessions as sess
from .services.receipts import process_due_jobs

PW = "demo1234"
PROV = "Sample illustration generated for demo — replace with your own photo"


def A(diet=(), spice=None, taste=(), tag=(), meal=(), texture=(), verified=True):
    out = [{"key": "diet", "value": d, "source": "restaurant_confirmed", "verified": verified} for d in diet]
    if spice is not None:
        out.append({"key": "spice", "value": str(spice), "source": "restaurant_confirmed", "verified": True})
    out += [{"key": "taste", "value": t, "source": "restaurant_confirmed", "verified": True} for t in taste]
    out += [{"key": "tag", "value": t, "source": "restaurant_confirmed", "verified": True} for t in tag]
    out += [{"key": "meal", "value": m, "source": "restaurant_confirmed", "verified": True} for m in meal]
    out += [{"key": "texture", "value": t, "source": "source_derived", "verified": False} for t in texture]
    return out


def mods(*groups):
    return [{"id": g[0], "name": g[1], "min": g[2], "max": g[3], "options": [{"id": f"{g[0]}-{i}", "name": n, "price_minor": p * 100} for i, (n, p) in enumerate(g[4])]} for g in groups]


class Builder:
    def __init__(self, db, r, menu):
        self.db, self.r, self.menu, self.cats, self.items = db, r, menu, {}, {}

    def cat(self, name, desc=""):
        c = Category(menu_id=self.menu.id, name=name, description=desc, sort=len(self.cats))
        self.db.add(c)
        self.db.flush()
        self.cats[name] = c
        return c

    def item(self, cat, name, price, desc, attrs=(), allergens=None, ingredients=None, state="available", stock=None, hue=30, modifiers=None):
        c = self.cats[cat]
        it = Item(menu_id=self.menu.id, category_id=c.id, name=name, description=desc, price_minor=price * 100, currency=self.r.currency, state=state, stock_remaining=stock, sort=len(self.items), attributes=list(attrs),
                  allergens={"verified": allergens is not None, "list": allergens or []}, ingredients={"verified": ingredients is not None, "list": ingredients or []},
                  image={"kind": "illustration", "hue": hue, "provenance": PROV}, modifier_groups=modifiers or [])
        self.db.add(it)
        self.db.flush()
        self.items[name] = it
        return it

    def rule(self, **kw):
        kw.setdefault("effect", "allow")
        self.db.add(AvailabilityRule(restaurant_id=self.r.id, **kw))


def mk_restaurant(db, **kw):
    r = Restaurant(is_demo=True, config=merged_config({}), **kw)
    db.add(r)
    db.flush()
    m = Menu(restaurant_id=r.id, name="Main menu", version=1, status="published", published_at=datetime.now(timezone.utc))
    db.add(m)
    db.flush()
    return r, Builder(db, r, m)


def mk_user(db, email, name, memberships, platform=False):
    u = db.query(User).filter(User.email == email).first() or User(email=email, name=name, password_hash=hash_password(PW), is_platform_admin=platform)
    db.add(u)
    db.flush()
    for r, role in memberships:
        db.add(Membership(user_id=u.id, restaurant_id=r.id, role=role))
    return u


def tables(db, r, labels):
    out = {}
    for lab, zone in labels:
        t = RestaurantTable(restaurant_id=r.id, label=lab, zone=zone)
        db.add(t)
        db.flush()
        db.add(QrCode(restaurant_id=r.id, table_id=t.id, token=public_token(16)))
        out[lab] = t
    return out


def direct_order(db, session, restaurant, lines, state="submitted", minutes_ago=0, when=None):
    """Seed-only: writes tickets without live availability checks, with the same data shape."""
    session.ticket_seq += 1
    number = (db.query(func.max(Order.number)).filter(Order.restaurant_id == restaurant.id).scalar() or 1000) + 1
    created = when or (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago))
    o = Order(restaurant_id=restaurant.id, session_id=session.id, number=number, ticket_seq=session.ticket_seq, ticket_type="original" if session.ticket_seq == 1 else "addon", state=state, idempotency_key=f"seed-{session.id[:6]}-{session.ticket_seq}-{number}", created_at=created)
    db.add(o)
    db.flush()
    for it, qty in lines:
        db.add(OrderItem(order_id=o.id, item_id=it.id, stable_key=it.stable_key, name_snapshot=it.name, unit_price_minor=it.price_minor, quantity=qty, line_total_minor=it.price_minor * qty))
    seq = (db.query(func.max(OrderStatusEvent.seq)).filter(OrderStatusEvent.restaurant_id == restaurant.id).scalar() or 0) + 1
    db.add(OrderStatusEvent(order_id=o.id, restaurant_id=restaurant.id, from_state=None, to_state=state if state in ("submitted",) else "submitted", actor="customer", at=created, seq=seq))
    if state != "submitted":
        db.add(OrderStatusEvent(order_id=o.id, restaurant_id=restaurant.id, from_state="submitted", to_state=state, actor="seed", at=created + timedelta(minutes=1), seq=seq + 1))
    return o


def history(db, r, b, tbl, days=14, per_day=(6, 14)):
    rng = random.Random(r.slug)
    items = list(b.items.values())
    t = list(tbl.values())
    for d in range(1, days + 1):
        for _ in range(rng.randint(*per_day)):
            when = datetime.now(timezone.utc) - timedelta(days=d, hours=rng.choice([-3, -2, -1, 0, 1, 2, 3, 5, 6]) , minutes=rng.randint(0, 59))
            s = TableSession(restaurant_id=r.id, table_id=rng.choice(t).id, public_token=public_token(12), state="closed", opened_at=when, closed_at=when + timedelta(hours=1))
            db.add(s)
            db.flush()
            direct_order(db, s, r, [(rng.choice(items), rng.randint(1, 2)) for _ in range(rng.randint(1, 3))], state="served", when=when)
    for _ in range(220):
        db.add(AnalyticsEvent(restaurant_id=r.id, event_type=rng.choice(["menu_view"] * 6 + ["dish_view"] * 5 + ["add_to_cart"] * 3 + ["rec_impression"] * 3 + ["rec_click"]), item_key=rng.choice(items).stable_key, session_ref=f"demo{rng.randint(1, 60):04d}", is_demo=True, at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 330))))


def seed(db):
    # ───────── Kettle & Crumb — café / bakery ─────────
    kc, b = mk_restaurant(db, slug="kettle-crumb", name="Kettle & Crumb", tagline="Slow mornings, fresh bakes, honest coffee.", venue_type="cafe_bakery", cuisine="Café · Bakery",
                          theme={"preset": "modern", "brand": "#1F3A5F", "brand_ink": "#FFFFFF", "accent": "#A8E0B5", "surface": "#F4F7F9", "radius": "round", "hero_style": "field"})
    r_hours = dict(restaurant_id=kc.id)
    b.rule(target_type="restaurant", kind="weekly", label="Open daily", days=[], start_time="07:30", end_time="19:00")
    b.rule(target_type="restaurant", kind="date_exception", effect="allow", label="Festive Sunday hours", start_date="2026-11-08", end_date="2026-11-08", start_time="10:00", end_time="14:00")
    for c, d in [("Breakfast", "Until 11:30"), ("Bakes", "Baked at dawn"), ("Sandwiches & Toasties", ""), ("Coffee & Tea", ""), ("Festive", "Limited season")]:
        b.cat(c, d)
    b.rule(target_type="category", target_id=b.cats["Breakfast"].stable_key, kind="weekly", label="Breakfast hours", days=[], start_time="07:30", end_time="11:30")
    b.item("Breakfast", "Masala Omelette Toast", 190, "Two-egg masala omelette folded into buttered sourdough toast.", A(["eggless"][:0] + [], 2, ["savory", "buttery"], ["comfort", "quick"], ["breakfast"]), ["egg", "gluten", "dairy"], ["egg", "onion", "green chilli", "sourdough", "butter"], hue=38)
    b.item("Breakfast", "Avocado Sourdough", 340, "Smashed avocado, lime, chilli flakes and seeds on toasted sourdough.", A(["vegetarian", "vegan"], 1, ["fresh", "creamy"], ["light"], ["breakfast"]), ["gluten", "sesame"], ["avocado", "sourdough", "lime", "chilli flakes", "seeds"], hue=110)
    b.item("Breakfast", "Granola & Curd Bowl", 240, "House granola, thick curd, seasonal fruit and honey.", A(["vegetarian"], 0, ["sweet", "crunchy", "fresh"], ["light"], ["breakfast"]), ["nuts", "dairy", "gluten"], None, hue=45)
    b.item("Breakfast", "Poha Plate", 150, "Flattened rice tempered with mustard, curry leaf and lemon.", A(["vegetarian", "vegan", "jain"][:2], 1, ["savory", "tangy"], ["comfort", "light"], ["breakfast"]), [], ["flattened rice", "onion", "peanuts", "curry leaf", "lemon"], hue=62)
    b.item("Bakes", "Butter Croissant", 120, "Laminated, shatteringly crisp, baked in small batches.", A(["vegetarian"], 0, ["buttery", "crisp"], ["indulgent"], ["breakfast", "snack"]), ["gluten", "dairy"], ["flour", "butter", "yeast", "sugar"], hue=40, stock=12)
    b.item("Bakes", "Almond Croissant", 160, "Frangipane-filled croissant with toasted almond flakes.", A(["vegetarian"], 0, ["sweet", "buttery"], ["indulgent"], ["snack", "dessert"]), ["gluten", "dairy", "nuts", "egg"], None, hue=32)
    b.item("Bakes", "Sourdough Loaf", 280, "48-hour fermented country loaf. Limited loaves each day.", A(["vegetarian", "vegan"], 0, ["tangy"], ["hearty"], ["snack"]), ["gluten"], ["flour", "water", "salt", "starter"], stock=4, hue=35)
    b.item("Bakes", "Dark Chocolate Brownie", 140, "Fudgy brownie, sea salt, 70% cocoa.", A(["vegetarian"], 0, ["sweet", "rich"], ["indulgent", "comfort"], ["dessert"]), None, None, hue=18)
    b.item("Bakes", "Lemon Tart", 170, "Buttery shell, tart lemon curd, torched meringue.", A(["vegetarian"], 0, ["tangy", "sweet"], ["light"], ["dessert"]), ["gluten", "dairy", "egg"], None, state="sold_out", hue=58)
    b.item("Sandwiches & Toasties", "Chilli Cheese Toastie", 210, "Three cheeses, green chilli and pickled onion, griddled crisp.", A(["vegetarian"], 2, ["savory", "creamy", "crunchy"], ["comfort", "quick"], ["lunch", "snack"]), ["gluten", "dairy"], None, hue=48)
    b.item("Sandwiches & Toasties", "Grilled Chicken Club", 320, "Herb chicken, lettuce, tomato and mayo on toasted white.", A([], 1, ["savory"], ["hearty"], ["lunch"]), ["gluten", "egg"], None, hue=25, modifiers=mods(("sides", "Add a side", 0, 1, [("Fries", 80), ("Side salad", 60)])))
    b.item("Coffee & Tea", "Filter Coffee", 90, "South-Indian style decoction with frothed milk.", A(["vegetarian"], 0, ["bitter", "sweet"], ["warm", "comfort"], ["drink"]), ["dairy"], None, hue=22)
    b.item("Coffee & Tea", "Flat White", 160, "Double ristretto, silky microfoam.", A(["vegetarian"], 0, ["bitter", "creamy"], ["warm"], ["drink"]), ["dairy"], None, hue=26, modifiers=mods(("milk", "Milk", 1, 1, [("Dairy", 0), ("Oat", 40)])))
    b.item("Coffee & Tea", "Cold Brew", 180, "Steeped 18 hours, served over ice.", A(["vegetarian", "vegan"], 0, ["bitter", "fresh"], ["cooling", "refreshing"], ["drink"]), [], None, hue=24)
    b.item("Coffee & Tea", "Masala Chai", 80, "Ginger, cardamom and black tea simmered with milk.", A(["vegetarian"], 1, ["spicy", "sweet"], ["warm", "comfort"], ["drink"]), ["dairy"], None, hue=30)
    b.item("Festive", "Festive Mithai Box", 450, "Six assorted festive sweets. Available during the season only.", A(["vegetarian"], 0, ["sweet", "rich"], ["festive", "shareable", "indulgent"], ["dessert"]), ["nuts", "dairy"], None, hue=15)
    b.rule(target_type="item", target_id=b.items["Festive Mithai Box"].stable_key, kind="season", label="Festive season", start_date="2026-10-15", end_date="2026-11-15")
    tk = tables(db, kc, [("1", "Window"), ("2", "Window"), ("3", "Counter"), ("4", "Garden")])
    history(db, kc, b, tk, per_day=(8, 16))
    db.add(RecommendationRule(restaurant_id=kc.id, target_type="item", target_id=b.items["Avocado Sourdough"].stable_key, weight=2, featured=True, label="Chef's pick"))
    mk_user(db, "owner@kettle.demo", "Kettle Owner", [(kc, "owner")])

    # ───────── Spice Route Kitchen — multi-cuisine ─────────
    sr, b = mk_restaurant(db, slug="spice-route", name="Spice Route Kitchen", tagline="North, South and a little Indo-Chinese — under one roof.", venue_type="multi_cuisine", cuisine="North Indian · South Indian · Indo-Chinese",
                          theme={"preset": "classic", "brand": "#7A1F2B", "brand_ink": "#FFFFFF", "accent": "#F2B705", "surface": "#FBF7F6", "radius": "soft", "hero_style": "field"})
    sr.config = merged_config({"service_charge_bps": 500, "tax": {"gst_bps": 500}, "ordering": {"allow_outside_hours": False}, "features": {"weather": True}})
    b.rule(target_type="restaurant", kind="weekly", label="Kitchen hours", days=[], start_time="11:00", end_time="23:00")
    for c in ["Starters", "North Indian Mains", "South Indian", "Indo-Chinese", "Breads & Rice", "Thalis", "Desserts", "Drinks"]:
        b.cat(c)
    b.item("Starters", "Paneer Tikka", 320, "Cottage cheese marinated in hung curd and spices, charred in the tandoor.", A(["vegetarian"], 2, ["smoky", "savory"], ["shareable"], ["dinner", "snack"]), ["dairy"], ["paneer", "curd", "spices", "capsicum"], hue=28)
    b.item("Starters", "Hara Bhara Kebab", 280, "Spinach and green-pea patties, pan-seared.", A(["vegetarian", "vegan"], 1, ["savory", "crisp"], ["light"], ["snack"]), [], ["spinach", "peas", "potato", "spices"], hue=100)
    b.item("Starters", "Chicken 65", 340, "Crisp fried chicken tossed with curry leaf and chilli.", A([], 3, ["spicy", "crunchy", "savory"], ["bold", "spicy"], ["snack", "dinner"]), None, None, hue=12)
    b.item("North Indian Mains", "Dal Makhani", 290, "Black lentils simmered overnight with butter and cream.", A(["vegetarian"], 1, ["rich", "creamy", "buttery"], ["comfort", "hearty"], ["lunch", "dinner"]), ["dairy"], ["black lentils", "butter", "cream", "tomato"], hue=20)
    b.item("North Indian Mains", "Butter Chicken", 420, "Tandoori chicken in a silky tomato-butter gravy.", A([], 1, ["rich", "creamy"], ["comfort", "hearty"], ["dinner"]), ["dairy", "nuts"], None, hue=14)
    b.item("North Indian Mains", "Kadhai Paneer", 340, "Paneer with peppers in a freshly ground kadhai masala.", A(["vegetarian"], 2, ["spicy", "savory"], ["bold"], ["lunch", "dinner"]), ["dairy"], None, hue=8)
    b.item("North Indian Mains", "Palak Dal", 240, "Spinach and yellow lentils with garlic tadka.", A(["vegetarian", "vegan", "jain"][:2], 1, ["savory"], ["light", "comfort"], ["lunch", "dinner"]), [], ["lentils", "spinach", "garlic", "cumin"], hue=105, state="available")
    b.item("South Indian", "Masala Dosa", 190, "Crisp rice-lentil crepe, spiced potato, sambar and chutneys.", A(["vegetarian", "vegan"], 1, ["crisp", "tangy", "savory"], ["comfort"], ["breakfast", "lunch", "dinner"]), [], ["rice", "lentils", "potato", "spices"], hue=44)
    b.item("South Indian", "Hyderabadi Dum Biryani", 380, "Fragrant basmati layered with slow-cooked chicken, sealed and steamed.", A([], 2, ["savory", "smoky"], ["hearty", "celebrate"], ["lunch", "dinner"]), ["dairy"], None, hue=36, stock=6)
    b.item("South Indian", "Curd Rice", 150, "Cooling curd rice with pomegranate and curry leaf.", A(["vegetarian"], 0, ["tangy", "creamy", "fresh"], ["cooling", "light", "comfort"], ["lunch"]), ["dairy"], None, hue=70)
    b.item("Indo-Chinese", "Veg Manchurian", 260, "Crisp vegetable dumplings in garlicky soy gravy.", A(["vegetarian"], 2, ["savory", "tangy"], ["bold"], ["dinner"]), ["soy", "gluten"], None, hue=18)
    b.item("Indo-Chinese", "Hakka Noodles", 250, "Wok-tossed noodles with crunchy vegetables.", A(["vegetarian"], 1, ["savory", "smoky"], ["quick"], ["lunch", "dinner"]), ["soy", "gluten", "egg"][:2], None, hue=50)
    b.item("Breads & Rice", "Butter Naan", 70, "Soft tandoor-baked bread brushed with butter.", A(["vegetarian"], 0, ["buttery", "soft"], ["comfort"], ["dinner"]), ["gluten", "dairy"], ["flour", "yoghurt", "butter"], hue=40)
    b.item("Breads & Rice", "Jeera Rice", 160, "Basmati tempered with cumin.", A(["vegetarian", "vegan"], 0, ["savory"], ["light"], ["lunch", "dinner"]), [], ["basmati", "cumin", "ghee"][:2], hue=64)
    b.item("Thalis", "Executive Lunch Thali", 360, "Dal, two sabzis, rice, roti, raita and a sweet. Served at lunch only.", A(["vegetarian"], 1, ["savory"], ["hearty", "comfort", "shareable"], ["lunch"]), ["dairy", "gluten"], None, hue=30)
    b.rule(target_type="item", target_id=b.items["Executive Lunch Thali"].stable_key, kind="weekly", label="Lunch", days=[0, 1, 2, 3, 4, 5], start_time="12:00", end_time="15:00")
    b.item("Desserts", "Gulab Jamun", 130, "Warm milk-solid dumplings in cardamom syrup (two pieces).", A(["vegetarian"], 0, ["sweet", "rich"], ["indulgent", "comfort"], ["dessert"]), ["dairy", "gluten", "nuts"], None, hue=14)
    b.item("Desserts", "Rasmalai", 160, "Soft cheese discs in saffron milk.", A(["vegetarian"], 0, ["sweet", "creamy"], ["indulgent"], ["dessert"]), ["dairy", "nuts"], None, state="sold_out", hue=48)
    b.item("Desserts", "Kulfi Falooda", 190, "Pistachio kulfi, rose syrup, vermicelli and basil seeds.", A(["vegetarian"], 0, ["sweet", "creamy", "fresh"], ["cooling", "refreshing", "festive"], ["dessert"]), ["dairy", "nuts"], None, hue=340)
    b.item("Drinks", "Sweet Lassi", 110, "Thick churned curd, sugar, a hint of cardamom.", A(["vegetarian"], 0, ["sweet", "creamy", "fresh"], ["cooling", "refreshing"], ["drink"]), ["dairy"], ["curd", "sugar", "cardamom"], hue=60)
    b.item("Drinks", "Fresh Lime Soda", 90, "Sweet, salted or mixed.", A(["vegetarian", "vegan"], 0, ["tangy", "fresh"], ["cooling", "refreshing"], ["drink"]), [], None, hue=95, modifiers=mods(("style", "Style", 1, 1, [("Sweet", 0), ("Salted", 0), ("Mixed", 0)])))
    b.item("Drinks", "Masala Chaas", 80, "Spiced buttermilk with roasted cumin.", A(["vegetarian"], 1, ["tangy", "fresh"], ["cooling"], ["drink"]), ["dairy"], None, hue=80)
    b.rule(target_type="restaurant", kind="date_exception", effect="block", label="Closed for Christmas Day", start_date="2026-12-25", end_date="2026-12-25")
    ts = tables(db, sr, [(str(i), "Main hall" if i <= 8 else "Terrace") for i in range(1, 13)])
    history(db, sr, b, ts)
    db.add(RecommendationRule(restaurant_id=sr.id, target_type="item", target_id=b.items["Dal Makhani"].stable_key, weight=2, featured=True, label="Chef's pick"))
    db.add(RecommendationRule(restaurant_id=sr.id, target_type="item", target_id=b.items["Chicken 65"].stable_key, weight=-1))
    mk_user(db, "owner@spiceroute.demo", "Spice Route Owner", [(sr, "owner")])
    mk_user(db, "manager@spiceroute.demo", "Spice Route Manager", [(sr, "manager")])
    mk_user(db, "kitchen@spiceroute.demo", "Spice Route Kitchen", [(sr, "kitchen")])
    mk_user(db, "staff@spiceroute.demo", "Spice Route Floor Staff", [(sr, "staff")])

    # Scenario E: Table 12 — Order A preparing, Add-on B just submitted.
    s12 = TableSession(restaurant_id=sr.id, table_id=ts["12"].id, public_token=public_token(24), state="open", contact_name="Demo Guest", contact_phone="+919999900001", consent_at=datetime.now(timezone.utc))
    db.add(s12)
    db.flush()
    direct_order(db, s12, sr, [(b.items["Paneer Tikka"], 1), (b.items["Butter Naan"], 2)], state="preparing", minutes_ago=14)
    direct_order(db, s12, sr, [(b.items["Gulab Jamun"], 1)], state="submitted", minutes_ago=1)
    # Table 5: a second open table at "ready"
    s5 = TableSession(restaurant_id=sr.id, table_id=ts["5"].id, public_token=public_token(24), state="open", contact_name="Sample Diner", contact_phone="+919999900002", consent_at=datetime.now(timezone.utc))
    db.add(s5)
    db.flush()
    direct_order(db, s5, sr, [(b.items["Masala Dosa"], 2), (b.items["Sweet Lassi"], 2)], state="ready", minutes_ago=22)

    # ───────── Copper Tap — bar / casual dining (food + non-alcoholic) ─────────
    ct, b = mk_restaurant(db, slug="copper-tap", name="Copper Tap", tagline="Bar bites, big burgers and zero-proof pours.", venue_type="bar_casual", cuisine="Gastropub · Mocktails",
                          theme={"preset": "friendly", "brand": "#14202B", "brand_ink": "#FFFFFF", "accent": "#E08A4B", "surface": "#F3F5F7", "radius": "soft", "hero_style": "split"})
    ct.config = merged_config({"tax": {"gst_bps": 1800}, "service_charge_bps": 1000})
    b.rule(target_type="restaurant", kind="weekly", label="Evenings (to 1 AM)", days=[], start_time="16:00", end_time="01:00")
    for c in ["Bar Bites", "Burgers & Pizza", "Mocktails", "Soft Pours"]:
        b.cat(c)
    b.item("Bar Bites", "Loaded Nachos", 320, "Corn chips, three-bean chilli, cheese sauce, jalapeño, salsa.", A(["vegetarian"], 2, ["savory", "crunchy", "creamy"], ["shareable", "indulgent"], ["snack", "dinner"]), ["dairy"], None, hue=44)
    b.item("Bar Bites", "Peri-Peri Fries", 190, "Skin-on fries dusted with peri-peri salt, garlic mayo dip.", A(["vegetarian"], 2, ["spicy", "crisp", "crunchy"], ["shareable", "quick"], ["snack"]), ["egg"], None, hue=22)
    b.item("Bar Bites", "Buffalo Wings", 360, "Six wings, buffalo glaze, blue-cheese style dip.", A([], 3, ["spicy", "tangy"], ["bold", "shareable"], ["snack"]), ["dairy"], None, hue=10)
    b.item("Burgers & Pizza", "Copper Smash Burger", 420, "Two smashed patties, cheddar, pickles, house sauce.", A([], 1, ["savory", "rich"], ["hearty", "indulgent"], ["dinner"]), ["gluten", "dairy", "egg"], None, hue=26, modifiers=mods(("extras", "Extras", 0, 2, [("Extra patty", 120), ("Bacon", 90), ("Fried egg", 40)])))
    b.item("Burgers & Pizza", "Crispy Veg Burger", 340, "Crunchy veg-and-cheese patty with chipotle mayo.", A(["vegetarian"], 1, ["savory", "crunchy"], ["hearty"], ["dinner"]), ["gluten", "dairy"], None, hue=88)
    b.item("Burgers & Pizza", "Margherita Pizza", 380, "San Marzano tomato, mozzarella, basil, 10-inch.", A(["vegetarian"], 0, ["savory", "tangy"], ["comfort", "shareable"], ["dinner"]), ["gluten", "dairy"], ["flour", "tomato", "mozzarella", "basil"], hue=12)
    b.item("Burgers & Pizza", "Smoked Chicken Pizza", 460, "Smoked chicken, red onion, mozzarella, BBQ drizzle.", A([], 1, ["smoky", "savory"], ["hearty"], ["dinner"]), None, None, hue=30, stock=5)
    b.item("Mocktails", "Virgin Mojito", 210, "Lime, mint, soda, crushed ice.", A(["vegetarian", "vegan"], 0, ["fresh", "tangy"], ["cooling", "refreshing"], ["drink"]), [], None, hue=130)
    b.item("Mocktails", "Spicy Guava Cooler", 230, "Guava, lime and a rim of chilli-salt.", A(["vegetarian", "vegan"], 1, ["tangy", "spicy", "fresh"], ["refreshing", "bold"], ["drink"]), [], None, hue=350)
    b.item("Mocktails", "Happy Hour Berry Fizz", 150, "Mixed-berry fizz. Happy hour price, 5–7 PM only.", A(["vegetarian", "vegan"], 0, ["sweet", "fresh"], ["refreshing"], ["drink"]), [], None, hue=310)
    b.rule(target_type="item", target_id=b.items["Happy Hour Berry Fizz"].stable_key, kind="weekly", label="Happy hour", days=[], start_time="17:00", end_time="19:00")
    b.item("Soft Pours", "Cold Coffee", 190, "Blended coffee, milk and vanilla ice cream.", A(["vegetarian"], 0, ["sweet", "creamy", "bitter"], ["indulgent", "cooling"], ["drink"]), ["dairy"], None, hue=24)
    b.item("Soft Pours", "Ginger Lemonade", 160, "Fresh ginger, lemon, light sweetness.", A(["vegetarian", "vegan"], 1, ["tangy", "fresh"], ["refreshing"], ["drink"]), [], None, hue=75)
    b.rule(target_type="restaurant", kind="date_exception", effect="block", label="Private event", start_date="2026-12-24", end_date="2026-12-24")
    tc = tables(db, ct, [("1", "Bar"), ("2", "Bar"), ("3", "Booth"), ("4", "Booth"), ("5", "Patio")])
    history(db, ct, b, tc, per_day=(5, 12))
    mk_user(db, "owner@coppertap.demo", "Copper Tap Owner", [(ct, "owner")])
    mk_user(db, "platform@foodmania.demo", "Platform Admin", [], platform=True)
    db.commit()

    # A paid session with receipt + notifications, produced through the real verified-event path.
    s3 = TableSession(restaurant_id=sr.id, table_id=ts["3"].id, public_token=public_token(24), state="open", contact_name="Paid Example", contact_phone="+919999900003", contact_email="paid.example@example.com", consent_at=datetime.now(timezone.utc))
    db.add(s3)
    db.flush()
    bi = {i.name: i for i in db.query(Item).join(Menu).filter(Menu.restaurant_id == sr.id).all()}
    direct_order(db, s3, sr, [(bi["Butter Chicken"], 1), (bi["Jeera Rice"], 1)], state="served", minutes_ago=75)
    db.commit()
    sess.request_bill(db, s3.id)
    pay, _ = sess.create_payment_session(db, s3.id, f"seed-{s3.id}")
    p = get_provider()
    body, sig = p.build_event(provider_ref=pay.provider_ref, amount_minor=pay.amount_minor, currency=pay.currency, outcome="success", event_id="evt_seed_paid")
    sess.handle_payment_event(db, "mock", {p.signature_header: sig}, body)
    # a second paid example whose email provider fails -> shows retry state
    s9 = TableSession(restaurant_id=sr.id, table_id=ts["9"].id, public_token=public_token(24), state="open", contact_name="Retry Example", contact_phone="+919999900009", contact_email="fail@example.com", consent_at=datetime.now(timezone.utc))
    db.add(s9)
    db.flush()
    direct_order(db, s9, sr, [(bi["Masala Dosa"], 1)], state="served", minutes_ago=50)
    db.commit()
    sess.request_bill(db, s9.id)
    pay9, _ = sess.create_payment_session(db, s9.id, f"seed-{s9.id}")
    body, sig = p.build_event(provider_ref=pay9.provider_ref, amount_minor=pay9.amount_minor, currency=pay9.currency, outcome="success", event_id="evt_seed_paid_2")
    sess.handle_payment_event(db, "mock", {p.signature_header: sig}, body)
    process_due_jobs(db)
    # sample guest reviews on the two paid examples (flagged simulated: they were left on a sample restaurant)
    from .models import Receipt, Review
    sample = [(5, "The Paneer Tikka was perfectly charred and the add-on dessert reached the table fast."), (4, "Great flavours, a little loud on a Friday. Loved that the bill was exact and instant.")]
    for rc, (rating, text) in zip(db.query(Receipt).filter(Receipt.restaurant_id == sr.id).order_by(Receipt.created_at).all(), sample):
        db.add(Review(restaurant_id=sr.id, receipt_id=rc.id, rating=rating, comment=text, guest_first_name=(rc.data.get("guest_first_name") or None), simulated=True))
    db.commit()


def reset(db_engine):
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if "--reset" in sys.argv:
        db.close()
        reset(engine)
        db = SessionLocal()
    if db.query(Restaurant).count():
        print("Database already has data. Use --reset to rebuild the demo data.")
        sys.exit(0)
    seed(db)
    print(f"Seeded demo data. All demo users share the password: {PW}")
