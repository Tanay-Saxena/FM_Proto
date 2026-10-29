from datetime import datetime, timezone
from types import SimpleNamespace as NS

from app.services.availability import RulesIndex, evaluate_item


def rule(**kw):
    base = dict(id="r", active=True, effect="allow", days=[], start_time=None, end_time=None, start_date=None, end_date=None, label="", target_id=None, kind="weekly", target_type="restaurant")
    base.update(kw)
    return NS(**base)


def setup(rules, tz="Asia/Kolkata", state="available", stock=None, accepting=True, outside=False):
    r = NS(timezone=tz, config={"ordering": {"accepting_orders": accepting, "allow_outside_hours": outside}})
    cat = NS(stable_key="cat1")
    item = NS(stable_key="item1", state=state, archived=False, stock_remaining=stock)
    return r, cat, item, RulesIndex.build(rules)


def at(s):  # UTC ISO
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


LUNCH = rule(target_type="item", target_id="item1", start_time="12:00", end_time="15:00", days=[0, 1, 2, 3, 4])


def test_window_boundaries_ist():
    r, c, i, idx = setup([LUNCH])
    # 2026-10-28 is a Wednesday. IST = UTC+5:30
    assert not evaluate_item(i, c, r, idx, at("2026-10-28T06:29:00Z")).orderable  # 11:59
    assert evaluate_item(i, c, r, idx, at("2026-10-28T06:30:00Z")).orderable  # 12:00 inclusive
    assert evaluate_item(i, c, r, idx, at("2026-10-28T09:29:00Z")).orderable  # 14:59
    assert not evaluate_item(i, c, r, idx, at("2026-10-28T09:30:00Z")).orderable  # 15:00 exclusive


def test_next_available_is_reported():
    r, c, i, idx = setup([LUNCH])
    av = evaluate_item(i, c, r, idx, at("2026-10-28T09:30:00Z"))
    assert av.status == "scheduled" and av.next_available_at.startswith("2026-10-29T12:00")


def test_weekday_filter():
    r, c, i, idx = setup([LUNCH])
    assert not evaluate_item(i, c, r, idx, at("2026-10-31T07:30:00Z")).orderable  # Saturday 13:00


def test_sold_out_and_pause_beat_schedule():
    for state, status in [("sold_out", "sold_out"), ("paused", "paused"), ("hidden", "hidden")]:
        r, c, i, idx = setup([LUNCH], state=state)
        av = evaluate_item(i, c, r, idx, at("2026-10-28T07:30:00Z"))
        assert (av.orderable, av.status) == (False, status)


def test_stock_zero_is_sold_out():
    r, c, i, idx = setup([], stock=0)
    assert evaluate_item(i, c, r, idx, at("2026-10-28T07:30:00Z")).status == "sold_out"


def test_date_block_exception_beats_weekly():
    ex = rule(kind="date_exception", effect="block", start_date="2026-10-28", end_date="2026-10-28")
    r, c, i, idx = setup([rule(start_time="09:00", end_time="23:00"), ex])
    assert not evaluate_item(i, c, r, idx, at("2026-10-28T07:30:00Z")).orderable


def test_allow_exception_overrides_weekly():
    weekly = rule(start_time="09:00", end_time="23:00")
    ex = rule(kind="date_exception", effect="allow", start_date="2026-11-08", end_date="2026-11-08", start_time="10:00", end_time="14:00")
    r, c, i, idx = setup([weekly, ex])
    assert evaluate_item(i, c, r, idx, at("2026-11-08T06:30:00Z")).orderable  # 12:00
    assert not evaluate_item(i, c, r, idx, at("2026-11-08T11:30:00Z")).orderable  # 17:00: weekly would allow, exception wins


def test_overnight_window_belongs_to_start_day():
    ov = rule(start_time="16:00", end_time="01:00", days=[2])  # Wednesday only
    r, c, i, idx = setup([ov])
    assert evaluate_item(i, c, r, idx, at("2026-10-28T19:00:00Z")).orderable  # Thu 00:30 IST (tail of Wed)
    assert not evaluate_item(i, c, r, idx, at("2026-10-29T19:00:00Z")).orderable  # Fri 00:30 (tail of Thu, not allowed)


def test_season_window():
    s = rule(target_type="item", target_id="item1", kind="season", start_date="2026-10-15", end_date="2026-11-15")
    r, c, i, idx = setup([s])
    assert evaluate_item(i, c, r, idx, at("2026-10-28T07:30:00Z")).orderable
    assert not evaluate_item(i, c, r, idx, at("2026-11-16T07:30:00Z")).orderable
    assert evaluate_item(i, c, r, idx, at("2026-11-15T17:30:00Z")).orderable  # last day inclusive


def test_dst_uses_local_wall_clock():
    lunch = rule(target_type="item", target_id="item1", start_time="12:00", end_time="15:00")
    r, c, i, idx = setup([lunch], tz="America/New_York")
    # before DST (EST, UTC-5) and after (EDT, UTC-4): 12:00 local both times
    assert evaluate_item(i, c, r, idx, at("2026-03-07T17:00:00Z")).orderable
    assert evaluate_item(i, c, r, idx, at("2026-03-09T16:00:00Z")).orderable
    assert evaluate_item(i, c, r, idx, at("2026-03-09T17:00:00Z")).orderable  # 13:00 EDT still inside
    assert not evaluate_item(i, c, r, idx, at("2026-03-09T19:00:00Z")).orderable  # 15:00 EDT


def test_restaurant_closed_blocks_unless_outside_hours_allowed():
    hours = rule(start_time="11:00", end_time="23:00")
    r, c, i, idx = setup([hours])
    night = at("2026-10-28T20:00:00Z")  # 01:30 IST
    assert evaluate_item(i, c, r, idx, night).status == "closed"
    r2, c2, i2, idx2 = setup([hours], outside=True)
    assert evaluate_item(i2, c2, r2, idx2, night).orderable


def test_not_accepting_orders():
    r, c, i, idx = setup([], accepting=False)
    assert evaluate_item(i, c, r, idx, at("2026-10-28T07:30:00Z")).status == "closed"
