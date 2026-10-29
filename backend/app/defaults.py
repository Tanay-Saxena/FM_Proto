"""Default restaurant configuration and theme tokens. Stored per restaurant in the database."""
import copy

DEFAULT_CONFIG = {
    "features": {"ai": True, "ordering": True, "reviews": False, "promotions": True, "weather": False},
    "tax": {"gst_bps": 500, "inclusive": False, "label": "GST"},
    "service_charge_bps": 0,
    "round_to_rupee": False,
    "ordering": {
        "accepting_orders": True,
        "allow_outside_hours": False,
        "contact_required": True,
        "auto_close_after_payment": True,
        "lock_on_bill_request": False,
    },
    "card_density": "comfortable",
    "templates": {
        "sms": "Thanks for dining at {restaurant}. Your receipt: {link}",
        "email_subject": "Your receipt from {restaurant}",
        "email_body": "Thank you for visiting {restaurant}.\nView your receipt: {link}",
    },
}

DEFAULT_THEME = {
    "preset": "modern",  # modern | classic | friendly
    "brand": "#12372A",
    "brand_ink": "#FFFFFF",
    "accent": "#F2B705",
    "surface": "#F7F8F5",
    "radius": "soft",  # sharp | soft | round
    "hero_style": "field",  # field | split
}


def merged_config(stored: dict | None) -> dict:
    out = copy.deepcopy(DEFAULT_CONFIG)

    def merge(a, b):
        for k, v in (b or {}).items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            else:
                a[k] = v

    merge(out, stored or {})
    return out


def merged_theme(stored: dict | None) -> dict:
    return {**DEFAULT_THEME, **(stored or {})}
