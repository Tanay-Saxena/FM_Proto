"""Ask-a-dish chat, grounded in the selected restaurant's current published menu."""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Restaurant
from ..providers.llm import get_llm
from ..schemas import Preferences
from .availability import evaluate_item
from .menu import published_menu, rules_index
from .recommend import ALLERGEN_SYNONYMS, _money, parse_query, rank, verified_diets

SAFETY = re.compile(r"allerg|contain|ingredient|made (?:with|of)|gluten|nut|dairy|egg|vegan|vegetarian|jain|halal|sugar|calorie|diabet", re.I)
PRICE = re.compile(r"how much|price|cost|cheap|expensive|₹|rs\b", re.I)
AVAIL = re.compile(r"available|serve|serving|when|sold out|stock|open", re.I)


def _find_dish(menu, message: str):
    msg = re.sub(r"[^a-z0-9 ]", " ", message.lower())
    best, best_score = None, 0
    for c in menu.categories:
        for it in c.items:
            name = re.sub(r"[^a-z0-9 ]", " ", it.name.lower())
            if name in msg:
                score = 100 + len(name)
            else:
                words = [w for w in name.split() if len(w) > 3]
                score = sum(len(w) for w in words if w in msg)
                if not words or score < max(5, sum(len(w) for w in words) * 0.6):
                    score = 0
            if score > best_score:
                best, best_score = (it, c), score
    return best


def _brief(it, av) -> dict:
    return {"id": it.id, "name": it.name, "price_minor": it.price_minor, "image": it.image, "orderable": av.orderable, "availability": av.as_dict()}


def answer(db: Session, restaurant: Restaurant, message: str, now: datetime) -> dict:
    menu = published_menu(db, restaurant.id)
    if not menu:
        return {"answer": "This restaurant hasn't published a menu yet.", "items": [], "grounded": True, "provider": "deterministic"}
    idx = rules_index(db, restaurant.id)
    found = _find_dish(menu, message)
    asked_allergens = sorted({canon for w, canon in ALLERGEN_SYNONYMS.items() if re.search(rf"\b{w}\b", message.lower())})

    if SAFETY.search(message) and found:
        it, c = found
        av = evaluate_item(it, c, restaurant, idx, now)
        diets = verified_diets(it)
        parts = []
        wants_diet = [d for d in ("vegan", "vegetarian", "jain", "eggless", "gluten_free") if re.search(d.replace("_", "[ -]?"), message.lower())]
        for d in wants_diet:
            if d in diets:
                parts.append(f"Yes — the restaurant confirms {it.name} is {d.replace('_', ' ')}.")
            else:
                parts.append(f"The menu doesn't confirm that {it.name} is {d.replace('_', ' ')}. Please ask the staff before ordering.")
        if asked_allergens or re.search(r"allerg|contain|gluten|nut|dairy|egg", message, re.I):
            al = it.allergens or {}
            if not al.get("verified"):
                parts.append(f"Allergen details for {it.name} haven't been verified by the restaurant, so I can't say what it contains or doesn't. Please check with the staff.")
            else:
                listed = [a.lower() for a in al.get("list", [])]
                if asked_allergens:
                    for a in asked_allergens:
                        parts.append(f"The restaurant lists {a} in {it.name}." if a in listed else f"The restaurant's verified allergen list for {it.name} does not include {a}. Cross-contact is still possible — tell the staff about any serious allergy.")
                else:
                    parts.append(f"Verified allergens for {it.name}: {', '.join(listed) if listed else 'none listed'}.")
        if re.search(r"ingredient|made (?:with|of)", message, re.I):
            ing = it.ingredients or {}
            parts.append(f"Ingredients per the restaurant: {', '.join(ing['list'])}." if ing.get("verified") and ing.get("list") else f"The menu doesn't list verified ingredients for {it.name}.")
        if not parts:
            parts.append(f"The menu has no verified detail on that for {it.name}. Please ask the staff.")
        return {"answer": " ".join(parts), "items": [_brief(it, av)], "grounded": True, "provider": "deterministic"}

    if found and PRICE.search(message):
        it, c = found
        av = evaluate_item(it, c, restaurant, idx, now)
        return {"answer": f"{it.name} is {_money(it.price_minor)}.", "items": [_brief(it, av)], "grounded": True, "provider": "deterministic"}

    if found and AVAIL.search(message):
        it, c = found
        av = evaluate_item(it, c, restaurant, idx, now)
        text = f"{it.name} is available right now." if av.orderable else f"{it.name} isn't orderable right now — {av.message.lower()}."
        return {"answer": text, "items": [_brief(it, av)], "grounded": True, "provider": "deterministic"}

    if SAFETY.search(message) and not found:
        prefs = parse_query(message)
        if prefs.diets or prefs.avoid_allergens:
            res = rank(db, restaurant, prefs, now)
            top = res["results"][:5]
            if top:
                label = ", ".join(prefs.diets + [f"no {a}" for a in prefs.avoid_allergens])
                return {"answer": f"These dishes are verified by the restaurant for: {label}. Dishes without verified details are left out rather than guessed.", "items": [_brief(r["item"], r["availability"]) for r in top], "grounded": True, "provider": "deterministic"}
            return {"answer": "I couldn't find any dish with verified details that fits that. Dishes with unverified diet or allergen data are excluded — please ask the staff.", "items": [], "grounded": True, "provider": "deterministic"}
        return {"answer": "Tell me which dish you mean and I'll share what the restaurant has verified. If the menu doesn't say, I won't guess.", "items": [], "grounded": True, "provider": "deterministic"}

    prefs = parse_query(message)
    res = rank(db, restaurant, prefs, now)
    top = res["results"][: prefs.limit]
    if not top:
        return {"answer": "I couldn't find anything on today's menu that matches. Try different words, or loosen the budget or diet filter.", "items": [], "grounded": True, "provider": "deterministic"}

    provider = "deterministic"
    text = "Here's what fits from today's menu: " + "; ".join(f"{r['item'].name} ({_money(r['item'].price_minor)})" for r in top[:3]) + "."
    llm = get_llm()
    if llm.name != "none":
        cand = {r["item"].id: {"name": r["item"].name, "price": _money(r["item"].price_minor), "description": r["item"].description, "why": r["reasons"]} for r in top}
        out = llm.complete(
            "You help diners choose from ONE restaurant's menu. Use only the candidates given. Never invent dishes, prices, ingredients or allergens. Reply as JSON: {\"answer\": string (max 60 words), \"dish_ids\": [ids from candidates]}.",
            f"Diner asked: {message}\nCandidates: {cand}",
        )
        if out and isinstance(out.get("answer"), str) and isinstance(out.get("dish_ids"), list):
            ids = [i for i in out["dish_ids"] if i in cand]
            if ids:
                text, provider = out["answer"][:500], llm.name
                top = [r for i in ids for r in top if r["item"].id == i] or top
    return {"answer": text, "items": [_brief(r["item"], r["availability"]) | {"reasons": r["reasons"][:3]} for r in top[:5]], "grounded": True, "provider": provider}
