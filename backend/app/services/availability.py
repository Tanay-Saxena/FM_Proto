"""Availability engine — the single source of truth for "can this be ordered right now?".

Used by menu display, recommendations, cart validation and order submission.

Precedence (documented in docs/DECISIONS.md D-007), first match wins:
 1. Item archived or state=hidden            -> hidden      (never shown, never orderable)
 2. Item state=paused                        -> paused
 3. Item state=sold_out or stock <= 0        -> sold_out
 4. Restaurant not accepting orders          -> closed
 5. For each level restaurant -> category -> item (restaurant hours skipped when the restaurant allows
    ordering outside hours):
      a. a matching BLOCK date exception closes the level
      b. else, if any ALLOW date exception covers today, the level is open only inside its window(s)
         (date exceptions override weekly schedules)
      c. else, if the level has weekly/season rules, it is open only inside one of them
      d. else the level is unconstrained
 6. Everything open -> available.
Window boundaries: start inclusive, end exclusive. Overnight windows (22:00-02:00) belong to the day
they start on. Times are evaluated as restaurant-local wall-clock time, so DST is handled by zoneinfo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..defaults import merged_config

LEVELS = ("restaurant", "category", "item")


@dataclass
class Availability:
    orderable: bool
    status: str  # available | paused | sold_out | hidden | closed | scheduled
    reason: str = ""
    message: str = ""
    next_available_at: str | None = None  # ISO, restaurant-local

    def as_dict(self) -> dict:
        return {
            "orderable": self.orderable,
            "status": self.status,
            "reason": self.reason,
            "message": self.message,
            "next_available_at": self.next_available_at,
        }


@dataclass
class RulesIndex:
    """Active rules for one restaurant, grouped by (target_type, target_id)."""

    by_target: dict[tuple[str, str | None], list] = field(default_factory=dict)

    @classmethod
    def build(cls, rules) -> "RulesIndex":
        idx = cls()
        for r in rules:
            if r.active:
                key = (r.target_type, r.target_id if r.target_type != "restaurant" else None)
                idx.by_target.setdefault(key, []).append(r)
        return idx

    def for_level(self, level: str, target_id: str | None) -> list:
        return self.by_target.get((level, target_id if level != "restaurant" else None), [])


def _t(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _date_in_range(rule, d: date) -> bool:
    if rule.start_date and d < _d(rule.start_date):
        return False
    if rule.end_date and d > _d(rule.end_date):
        return False
    return True


def _window_matches(rule, ldt: datetime) -> bool:
    """Is local datetime inside this rule's weekday+time window? (date range checked separately)."""
    days = rule.days or []
    if not rule.start_time or not rule.end_time:
        return not days or ldt.weekday() in days
    st, et, t = _t(rule.start_time), _t(rule.end_time), ldt.time()
    if st == et:
        return not days or ldt.weekday() in days
    if st < et:
        return (not days or ldt.weekday() in days) and st <= t < et
    # overnight window
    if t >= st:
        return not days or ldt.weekday() in days
    if t < et:
        return not days or ((ldt.weekday() - 1) % 7) in days
    return False


def _overnight_prev_date_ok(rule, ldt: datetime) -> bool:
    """For the after-midnight tail of an overnight window, date ranges apply to the starting day."""
    if rule.start_time and rule.end_time and _t(rule.start_time) > _t(rule.end_time) and ldt.time() < _t(rule.end_time):
        return _date_in_range(rule, (ldt - timedelta(days=1)).date())
    return _date_in_range(rule, ldt.date())


def level_open(rules: list, ldt: datetime) -> tuple[bool, str]:
    if not rules:
        return True, ""
    exceptions = [r for r in rules if r.kind == "date_exception"]
    for r in exceptions:
        if r.effect == "block" and _date_in_range(r, ldt.date()) and (
            not r.start_time or not r.end_time or _window_matches(r, ldt)
        ):
            return False, r.label or "closed_date"
    allow_ex = [r for r in exceptions if r.effect == "allow" and _date_in_range(r, ldt.date())]
    if allow_ex:
        ok = any(_window_matches(r, ldt) for r in allow_ex)
        return ok, "" if ok else "outside_exception_hours"
    schedule = [r for r in rules if r.kind in ("weekly", "season") and r.effect == "allow"]
    if schedule:
        ok = any(_overnight_prev_date_ok(r, ldt) and _window_matches(r, ldt) for r in schedule)
        return ok, "" if ok else "outside_schedule"
    return True, ""


def _levels_for(item, category, idx: RulesIndex, skip_restaurant: bool):
    levels = []
    if not skip_restaurant:
        levels.append(("restaurant", idx.for_level("restaurant", None)))
    levels.append(("category", idx.for_level("category", category.stable_key)))
    levels.append(("item", idx.for_level("item", item.stable_key)))
    return levels


def _time_open(levels, ldt: datetime) -> tuple[bool, str, str]:
    for name, rules in levels:
        ok, why = level_open(rules, ldt)
        if not ok:
            return False, name, why
    return True, "", ""


def _next_open(levels, tz: ZoneInfo, now_local: datetime) -> datetime | None:
    rules = [r for _, rs in levels for r in rs]
    candidates: set[datetime] = set()
    for day in range(0, 15):
        d = (now_local + timedelta(days=day)).date()
        candidates.add(datetime.combine(d, time(0, 0), tzinfo=tz))
        for r in rules:
            if r.start_time:
                candidates.add(datetime.combine(d, _t(r.start_time), tzinfo=tz))
    for c in sorted(candidates):
        if c > now_local and _time_open(levels, c)[0]:
            return c
    return None


def _fmt_next(nxt: datetime, now_local: datetime) -> str:
    return nxt.isoformat(timespec="minutes")


def evaluate_item(item, category, restaurant, idx: RulesIndex, now: datetime | None = None) -> Availability:
    cfg = merged_config(restaurant.config)
    tz = ZoneInfo(restaurant.timezone)
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(tz)

    if item.archived or item.state == "hidden":
        return Availability(False, "hidden", "hidden", "Not on the menu")
    if item.state == "paused":
        return Availability(False, "paused", "paused", "Paused by the restaurant")
    if item.state == "sold_out" or (item.stock_remaining is not None and item.stock_remaining <= 0):
        return Availability(False, "sold_out", "sold_out", "Sold out")
    if not cfg["ordering"]["accepting_orders"]:
        return Availability(False, "closed", "not_accepting", "Not taking orders right now")

    skip_restaurant = bool(cfg["ordering"]["allow_outside_hours"])
    levels = _levels_for(item, category, idx, skip_restaurant)
    ok, level, why = _time_open(levels, now_local)
    if ok:
        return Availability(True, "available")

    nxt = _next_open(levels, tz, now_local)
    nxt_iso = _fmt_next(nxt, now_local) if nxt else None
    if level == "restaurant":
        status, reason = "closed", why or "closed_hours"
        msg = "Kitchen is closed" if not nxt else "Kitchen opens " + _human(nxt, now_local)
    else:
        status, reason = "scheduled", why or "outside_schedule"
        msg = "Not served right now" if not nxt else "Available " + _human(nxt, now_local)
    return Availability(False, status, reason, msg, nxt_iso)


def _human(nxt: datetime, now_local: datetime) -> str:
    clock = nxt.strftime("%-I:%M %p").replace(":00 ", " ").lower()
    delta_days = (nxt.date() - now_local.date()).days
    if delta_days == 0:
        return f"today at {clock}"
    if delta_days == 1:
        return f"tomorrow at {clock}"
    return f"{nxt.strftime('%a %-d %b')} at {clock}"


def restaurant_is_open(restaurant, idx: RulesIndex, now: datetime | None = None) -> dict:
    cfg = merged_config(restaurant.config)
    tz = ZoneInfo(restaurant.timezone)
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)
    if not cfg["ordering"]["accepting_orders"]:
        return {"open": False, "message": "Not taking orders right now", "next_open_at": None}
    levels = [("restaurant", idx.for_level("restaurant", None))]
    ok, _, why = _time_open(levels, now_local)
    if ok:
        return {"open": True, "message": "Open now", "next_open_at": None}
    nxt = _next_open(levels, tz, now_local)
    return {
        "open": False,
        "message": ("Closed today" if why not in ("outside_schedule", "outside_exception_hours") else "Closed")
        + (f" · opens {_human(nxt, now_local)}" if nxt else ""),
        "next_open_at": nxt.isoformat(timespec="minutes") if nxt else None,
    }
