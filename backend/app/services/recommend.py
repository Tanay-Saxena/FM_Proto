"""Deterministic, explainable recommendation engine (no vector search by design — spec M06).

Pipeline (docs/DECISIONS.md D-008):
  1. HARD FILTERS (never overridden by boosts): published menu of THIS restaurant, orderable now,
     budget, VERIFIED dietary needs, VERIFIED allergen safety, admin 'allow_in_recommendations'.
  2. PREFERENCE SCORE from taste / meal / mood / query text / spice / optional weather.
  3. ADMIN BOOST bounded to [-5, +5], applied only to items that survived step 1.
  4. Sort by (score desc, name asc) so results are reproducible; explain with grounded reasons.
"""
from __future__ import annotations

import random
import re
from datetime import datetime

from sqlalchemy.orm import Session

from ..defaults import merged_config
from ..models import Restaurant
from ..schemas import Preferences
from .availability import evaluate_item
from .menu import active_recommendation_rules, published_menu, rules_index

DIET_IMPLIES = {"vegan": {"vegan", "vegetarian", "eggless"}, "jain": {"jain", "vegetarian"}}
SOURCE_WEIGHT = {"restaurant_confirmed": 3, "source_derived": 2, "ai_suggested": 1}
MOODS = {
    "comfort": {"comfort", "hearty", "warm"},
    "light": {"light", "fresh"},
    "celebrate": {"indulgent", "festive", "shareable"},
    "quick": {"quick", "snack"},
    "adventurous": {"bold", "spicy", "chef_special"},
}
TASTES = {"sweet", "savory", "tangy", "creamy", "crunchy", "smoky", "spicy", "rich", "fresh", "bitter", "buttery", "soft", "crisp"}
ALLERGEN_SYNONYMS = {
    "nuts": "nuts", "nut": "nuts", "peanut": "nuts", "peanuts": "nuts", "almond": "nuts", "cashew": "nuts",
    "dairy": "dairy", "milk": "dairy", "lactose": "dairy", "gluten": "gluten", "wheat": "gluten",
    "egg": "egg", "eggs": "egg", "soy": "soy", "fish": "fish", "shellfish": "shellfish", "prawn": "shellfish",
    "sesame": "sesame", "mustard": "mustard",
}
STOP = {"the", "and", "with", "for", "want", "something", "like", "some", "give", "show", "can", "have", "get", "what", "are", "any", "you", "please", "under", "below", "less", "than", "food", "dish", "dishes", "eat", "good", "best", "need", "looking", "that", "this", "has", "does", "contain", "contains", "free"}


def item_attr_values(item, key: str, verified_only=False) -> list[tuple[str, str, bool]]:
    return [(a["value"], a.get("source", "restaurant_confirmed"), bool(a.get("verified"))) for a in item.attributes if a.get("key") == key and (a.get("verified") or not verified_only)]


def verified_diets(item) -> set[str]:
    out: set[str] = set()
    for value, _, ok in item_attr_values(item, "diet"):
        if ok:
            out |= DIET_IMPLIES.get(value, {value})
    return out


def parse_query(text: str) -> Preferences:
    """Pull constraints out of natural language. Returns only what was clearly stated."""
    t = text.lower()
    diets = [d for d, pat in {
        "vegan": r"\bvegan\b", "jain": r"\bjain\b", "eggless": r"\beggless\b|\bwithout egg", "gluten_free": r"gluten[ -]?free",
        "vegetarian": r"\bveg\b|\bvegetarian\b|\bpure veg\b",
    }.items() if re.search(pat, t)]
    avoid = sorted({
        canon for w, canon in ALLERGEN_SYNONYMS.items()
        if re.search(rf"\b(?:no|without|avoid|allergic to|allergy to)\s+(?:any\s+)?{w}\b|\b{w}[- ]free\b|\b{w} allergy\b", t)
    })
    m = re.search(r"(?:under|below|less than|within|upto|up to|budget(?: of)?|max)\s*(?:₹|rs\.?|inr)?\s*(\d{2,5})", t) or re.search(r"(?:₹|rs\.?)\s*(\d{2,5})", t)
    budget = int(m.group(1)) * 100 if m else None
    spice = 0 if re.search(r"\bno spice|not spicy|non[- ]spicy|plain\b", t) else 1 if re.search(r"\bmild\b", t) else 3 if re.search(r"\bvery spicy|extra spicy|fiery|\bhot and spicy", t) else None
    tastes = sorted({w for w in TASTES if re.search(rf"\b{w}\b", t)})
    mood = next((k for k, syn in {"comfort": {"comfort", "cozy", "cosy", "homely", "hearty"}, "light": {"light", "healthy", "fresh"}, "celebrate": {"celebrate", "treat", "indulge", "festive"}, "quick": {"quick", "fast", "snack"}, "adventurous": {"adventurous", "bold", "surprise", "different"}}.items() if any(re.search(rf"\b{s}", t) for s in syn)), None)
    meal = next((m_ for m_ in ("breakfast", "lunch", "dinner", "dessert", "snack", "drink") if re.search(rf"\b{m_}", t)), None)
    if meal is None and re.search(r"\b(coffee|tea|juice|mocktail|shake|beverage|drink)", t):
        meal = "drink"
    return Preferences(query=text, diets=diets, avoid_allergens=avoid, max_price_minor=budget, max_spice=spice, tastes=tastes, mood=mood, meal=meal)


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP and w not in ALLERGEN_SYNONYMS and w not in TASTES]


def _money(minor: int) -> str:
    return f"₹{minor / 100:,.0f}" if minor % 100 == 0 else f"₹{minor / 100:,.2f}"


def rank(db: Session, restaurant: Restaurant, prefs: Preferences, now: datetime, *, for_random=False) -> dict:
    cfg = merged_config(restaurant.config)
    menu = published_menu(db, restaurant.id)
    idx = rules_index(db, restaurant.id)
    rules = active_recommendation_rules(db, restaurant.id, now)
    item_rules: dict[str, list] = {}
    cat_rules: dict[str, list] = {}
    for r in rules:
        (item_rules if r.target_type == "item" else cat_rules).setdefault(r.target_id, []).append(r)

    excluded = {"unavailable": 0, "over_budget": 0, "diet_unverified": 0, "allergen_unverified": 0, "admin_hidden": 0}
    results = []
    tokens = _tokens(prefs.query)
    for cat in (menu.categories if menu else []):
        for it in cat.items:
            av = evaluate_item(it, cat, restaurant, idx, now)
            if not av.orderable:
                excluded["unavailable"] += 1
                continue
            applicable = item_rules.get(it.stable_key, []) + cat_rules.get(cat.stable_key, [])
            if any(not r.allow_in_recommendations for r in applicable):
                excluded["admin_hidden"] += 1
                continue
            if prefs.max_price_minor is not None and it.price_minor > prefs.max_price_minor:
                excluded["over_budget"] += 1
                continue
            have = verified_diets(it)
            if any(d not in have for d in prefs.diets):
                excluded["diet_unverified"] += 1
                continue
            if prefs.avoid_allergens:
                al = it.allergens or {}
                listed = {a.lower() for a in al.get("list", [])}
                if not al.get("verified") or listed & set(prefs.avoid_allergens):
                    excluded["allergen_unverified"] += 1
                    continue

            score, reasons = 0.0, []
            for d in prefs.diets:
                reasons.append(f"{d.replace('_', ' ').title()} — confirmed by the restaurant")
            if prefs.avoid_allergens:
                reasons.append("Allergens verified: none of " + ", ".join(prefs.avoid_allergens))
            if prefs.max_price_minor is not None:
                reasons.append(f"{_money(it.price_minor)}, within your budget")
            for t in prefs.tastes:
                for v, src, ok in item_attr_values(it, "taste"):
                    if v == t:
                        score += SOURCE_WEIGHT.get(src, 1)
                        reasons.append(f"Tastes {t}" + ("" if ok else " (not yet confirmed)"))
            if prefs.mood:
                want = MOODS.get(prefs.mood, set())
                hits = [v for k in ("tag", "taste") for v, _, _ in item_attr_values(it, k) if v in want]
                if hits:
                    score += 2 * len(set(hits))
                    reasons.append(f"Fits a {prefs.mood} mood")
            if prefs.meal and any(v == prefs.meal for v, _, _ in item_attr_values(it, "meal")):
                score += 3
                reasons.append(f"A {prefs.meal} favourite on this menu")
            name_l, desc_l = it.name.lower(), it.description.lower()
            attr_text = " ".join(a["value"] for a in it.attributes).lower()
            for tok in tokens:
                if tok in name_l:
                    score += 3
                    reasons.append(f"Matches “{tok}”")
                elif tok in attr_text:
                    score += 2
                elif tok in desc_l:
                    score += 1
            spice = next((int(v) for v, _, _ in item_attr_values(it, "spice") if v.isdigit()), None)
            if prefs.max_spice is not None and spice is not None:
                if spice <= prefs.max_spice:
                    score += 1
                else:
                    score -= 3
            if prefs.weather and cfg["features"].get("weather"):
                tags = {v for k in ("tag", "taste") for v, _, _ in item_attr_values(it, k)}
                want = {"hot": {"cooling", "refreshing", "cold"}, "cold": {"warm", "comfort", "hearty"}, "rainy": {"warm", "comfort", "hearty"}}[prefs.weather]
                if tags & want:
                    score += 2
                    reasons.append(f"Suits {prefs.weather} weather")

            boost = max(-5, min(5, sum(r.weight for r in applicable)))
            promo = next((r for r in applicable if r.featured or r.label), None)
            if promo and promo.label:
                reasons.append(f"Restaurant's pick: {promo.label}")
            results.append(
                {
                    "item": it,
                    "category": cat,
                    "availability": av,
                    "score": round(score + boost, 2),
                    "preference_score": round(score, 2),
                    "boost": boost,
                    "reasons": list(dict.fromkeys(reasons)),
                    "promo": {"label": promo.label or "Featured", "featured": promo.featured} if promo else None,
                }
            )
    results.sort(key=lambda r: (-r["score"], r["item"].name))
    return {"results": results, "excluded": excluded}


def surprise(db: Session, restaurant: Restaurant, prefs: Preferences, now: datetime, rng: random.Random | None = None):
    """Random pick with exactly the same eligibility as recommendations."""
    ranked = rank(db, restaurant, prefs, now, for_random=True)["results"]
    if not ranked:
        return None
    rng = rng or random.Random()
    return rng.choice(ranked)
