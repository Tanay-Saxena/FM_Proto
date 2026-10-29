from types import SimpleNamespace as NS

from app.services.billing import compute_bill, round_half_up


def order(state, lines, seq=1):
    items = [NS(name_snapshot=n, quantity=q, unit_price_minor=p, line_total_minor=p * q, modifiers=[]) for n, q, p in lines]
    return NS(id=f"o{seq}", number=1000 + seq, ticket_seq=seq, ticket_type="original" if seq == 1 else "addon", state=state, items=items, label=chr(64 + seq))


def rest(**cfg):
    return NS(currency="INR", config=cfg)


def test_rounding_half_up():
    assert round_half_up(5, 10) == 1 and round_half_up(4, 10) == 0 and round_half_up(15, 10) == 2


def test_exclusive_tax_and_service():
    b = compute_bill(rest(service_charge_bps=500, tax={"gst_bps": 500}), [order("served", [("A", 2, 32000)]), order("submitted", [("B", 1, 13000)], 2)])
    assert b["subtotal_minor"] == 77000
    assert b["service_charge_minor"] == 3850
    assert b["tax_minor"] == round_half_up((77000 + 3850) * 500, 10000)
    assert b["total_minor"] == 77000 + 3850 + b["tax_minor"]


def test_rejected_and_cancelled_never_billed():
    b = compute_bill(rest(), [order("served", [("A", 1, 10000)]), order("rejected", [("B", 1, 99900)], 2), order("cancelled", [("C", 1, 5000)], 3)])
    assert b["subtotal_minor"] == 10000 and len(b["excluded_tickets"]) == 2


def test_inclusive_tax_not_added():
    b = compute_bill(rest(tax={"gst_bps": 500, "inclusive": True}), [order("served", [("A", 1, 10500)])])
    assert b["total_minor"] == 10500 and b["tax_minor"] == 500


def test_round_to_rupee():
    b = compute_bill(rest(tax={"gst_bps": 500}, round_to_rupee=True), [order("served", [("A", 1, 12345)])])
    assert b["total_minor"] % 100 == 0
