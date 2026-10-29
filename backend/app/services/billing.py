"""Server-side bill calculation from authoritative order records. Exact integer arithmetic only.

Policy (docs/DECISIONS.md D-009):
  subtotal        = sum of billable order lines (name/price snapshots, incl. modifier deltas)
  service charge  = round_half_up(subtotal * service_bps / 10_000)
  tax (exclusive) = round_half_up((subtotal + service) * gst_bps / 10_000)   -> added on top
  tax (inclusive) = portion already contained in (subtotal + service)         -> not added
  rounding        = optional adjustment to the nearest whole currency unit
Rejected and cancelled tickets are never billable. Discounts are not implemented.
"""
from ..defaults import merged_config

NON_BILLABLE = {"rejected", "cancelled"}


def round_half_up(num: int, den: int) -> int:
    return (2 * num + den) // (2 * den)


def compute_bill(restaurant, orders) -> dict:
    cfg = merged_config(restaurant.config)
    tickets, excluded = [], []
    subtotal = 0
    for o in sorted(orders, key=lambda o: o.ticket_seq):
        if o.state in NON_BILLABLE:
            excluded.append({"order_id": o.id, "number": o.number, "label": o.label, "state": o.state})
            continue
        lines = [
            {
                "name": i.name_snapshot,
                "quantity": i.quantity,
                "unit_price_minor": i.unit_price_minor,
                "line_total_minor": i.line_total_minor,
                "modifiers": i.modifiers,
            }
            for i in o.items
        ]
        t_sub = sum(l["line_total_minor"] for l in lines)
        subtotal += t_sub
        tickets.append(
            {
                "order_id": o.id,
                "number": o.number,
                "label": o.label,
                "ticket_type": o.ticket_type,
                "state": o.state,
                "items": lines,
                "subtotal_minor": t_sub,
            }
        )
    sc_bps = int(cfg["service_charge_bps"])
    service = round_half_up(subtotal * sc_bps, 10_000)
    gst_bps = int(cfg["tax"]["gst_bps"])
    taxable = subtotal + service
    if cfg["tax"]["inclusive"]:
        tax = round_half_up(taxable * gst_bps, 10_000 + gst_bps)
        total = taxable
    else:
        tax = round_half_up(taxable * gst_bps, 10_000)
        total = taxable + tax
    rounding = 0
    if cfg["round_to_rupee"] and total:
        rounding = round_half_up(total, 100) * 100 - total
        total += rounding
    return {
        "currency": restaurant.currency,
        "tickets": tickets,
        "excluded_tickets": excluded,
        "subtotal_minor": subtotal,
        "service_charge_bps": sc_bps,
        "service_charge_minor": service,
        "tax_label": cfg["tax"].get("label", "Tax"),
        "tax_bps": gst_bps,
        "tax_inclusive": bool(cfg["tax"]["inclusive"]),
        "tax_minor": tax,
        "rounding_minor": rounding,
        "total_minor": total,
        "item_count": sum(i["quantity"] for t in tickets for i in t["items"]),
    }
