"""Pydantic request models (validation at the API boundary)."""
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

StrList = list[str]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class ThemeTokens(BaseModel):
    preset: Literal["modern", "classic", "friendly"] = "modern"
    brand: str = "#12372A"
    brand_ink: str = "#FFFFFF"
    accent: str = "#F2B705"
    surface: str = "#F7F8F5"
    radius: Literal["sharp", "soft", "round"] = "soft"
    hero_style: Literal["field", "split"] = "field"

    @field_validator("brand", "brand_ink", "accent", "surface")
    @classmethod
    def _hex(cls, v):
        if not HEX.match(v):
            raise ValueError("must be a #RRGGBB colour")
        return v.upper()


class RestaurantPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    tagline: str | None = Field(None, max_length=240)
    cuisine: str | None = Field(None, max_length=120)
    timezone: str | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)
    theme: ThemeTokens | None = None
    config: dict | None = None


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,60}$")
    venue_type: str = "restaurant"
    cuisine: str = ""
    timezone: str = "Asia/Kolkata"
    currency: str = Field("INR", min_length=3, max_length=3)
    owner_email: str
    owner_password: str = Field(min_length=8)


class ModifierOption(BaseModel):
    id: str = Field(max_length=40)
    name: str = Field(max_length=80)
    price_minor: int = Field(0, ge=0, le=10_000_00)


class ModifierGroup(BaseModel):
    id: str = Field(max_length=40)
    name: str = Field(max_length=80)
    min: int = Field(0, ge=0, le=10)
    max: int = Field(1, ge=1, le=10)
    options: list[ModifierOption] = Field(max_length=30)


class Attribute(BaseModel):
    key: Literal["diet", "spice", "taste", "texture", "tag", "meal"]
    value: str = Field(max_length=40)
    source: Literal["restaurant_confirmed", "source_derived", "ai_suggested"] = "restaurant_confirmed"
    verified: bool = False


class VerifiedList(BaseModel):
    verified: bool = False
    list: StrList = Field(default_factory=list, max_length=40)


class ImageInfo(BaseModel):
    kind: Literal["illustration", "photo"] = "illustration"
    hue: int = Field(30, ge=0, le=360)
    url: str | None = Field(None, max_length=500)
    provenance: str = Field("Sample illustration generated for demo", max_length=200)

    @field_validator("url")
    @classmethod
    def _url(cls, v):
        if v and not re.match(r"^https://", v):
            raise ValueError("image url must be https")
        return v


class ItemIn(BaseModel):
    category_id: str
    name: str = Field(min_length=1, max_length=160)
    description: str = Field("", max_length=1200)
    price_minor: int = Field(ge=0, le=10_000_000)
    state: Literal["available", "paused", "sold_out", "hidden"] = "available"
    stock_remaining: int | None = Field(None, ge=0, le=100000)
    attributes: list[Attribute] = Field(default_factory=list, max_length=40)
    allergens: VerifiedList = Field(default_factory=VerifiedList)
    ingredients: VerifiedList = Field(default_factory=VerifiedList)
    image: ImageInfo = Field(default_factory=ImageInfo)
    modifier_groups: list[ModifierGroup] = Field(default_factory=list, max_length=10)


class ItemPatch(BaseModel):
    category_id: str | None = None
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=1200)
    price_minor: int | None = Field(None, ge=0, le=10_000_000)
    state: Literal["available", "paused", "sold_out", "hidden"] | None = None
    stock_remaining: int | None = Field(None, ge=0, le=100000)
    clear_stock: bool = False
    sort: int | None = None
    archived: bool | None = None
    attributes: list[Attribute] | None = None
    allergens: VerifiedList | None = None
    ingredients: VerifiedList | None = None
    image: ImageInfo | None = None
    modifier_groups: list[ModifierGroup] | None = None


class BulkItems(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=200)
    state: Literal["available", "paused", "sold_out", "hidden"] | None = None
    archived: bool | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field("", max_length=240)
    sort: int | None = None


class AvailabilityRuleIn(BaseModel):
    target_type: Literal["restaurant", "category", "item"]
    target_id: str | None = None
    kind: Literal["weekly", "date_exception", "season"]
    effect: Literal["allow", "block"] = "allow"
    label: str = Field("", max_length=80)
    days: list[int] = Field(default_factory=list, max_length=7)
    start_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    start_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    active: bool = True

    @field_validator("days")
    @classmethod
    def _days(cls, v):
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("days must be 0 (Mon) to 6 (Sun)")
        return sorted(set(v))


class AvailabilityRulePatch(BaseModel):
    label: str | None = None
    effect: Literal["allow", "block"] | None = None
    days: list[int] | None = None
    start_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    start_date: str | None = None
    end_date: str | None = None
    active: bool | None = None


class RecommendationRuleIn(BaseModel):
    target_type: Literal["item", "category"]
    target_id: str
    weight: int = Field(0, ge=-5, le=5)
    featured: bool = False
    label: str = Field("", max_length=60)
    allow_in_recommendations: bool = True
    start_at: datetime | None = None
    end_at: datetime | None = None
    active: bool = True


class RecommendationRulePatch(BaseModel):
    weight: int | None = Field(None, ge=-5, le=5)
    featured: bool | None = None
    label: str | None = Field(None, max_length=60)
    allow_in_recommendations: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    active: bool | None = None


class TableIn(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    zone: str = Field("", max_length=60)


class Preferences(BaseModel):
    query: str = Field("", max_length=300)
    diets: list[Literal["vegetarian", "vegan", "jain", "eggless", "gluten_free"]] = Field(default_factory=list)
    avoid_allergens: list[str] = Field(default_factory=list, max_length=12)
    max_price_minor: int | None = Field(None, ge=0, le=10_000_000)
    max_spice: int | None = Field(None, ge=0, le=3)
    tastes: list[str] = Field(default_factory=list, max_length=8)
    mood: str | None = Field(None, max_length=30)
    meal: str | None = Field(None, max_length=30)
    weather: Literal["hot", "cold", "rainy"] | None = None
    limit: int = Field(6, ge=1, le=20)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[dict] = Field(default_factory=list, max_length=10)


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    email: EmailStr | None = None
    consent: bool

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        digits = re.sub(r"[\s\-()]", "", v)
        if not re.fullmatch(r"\+?\d{7,15}", digits):
            raise ValueError("enter a valid mobile number")
        return digits


class CartLine(BaseModel):
    item_id: str
    quantity: int = Field(ge=1, le=20)
    modifier_option_ids: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field("", max_length=200)


class OrderIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)
    lines: list[CartLine] = Field(min_length=1, max_length=40)
    notes: str = Field("", max_length=300)


class TransitionIn(BaseModel):
    to_state: Literal["accepted", "preparing", "ready", "served", "rejected", "cancelled"]
    reason: str = Field("", max_length=200)


class PaymentSessionIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=80)


class MockCheckoutIn(BaseModel):
    outcome: Literal["success", "failure", "cancel"]


class StaffIn(BaseModel):
    email: str = Field(max_length=200)
    name: str = Field("", max_length=120)
    password: str | None = Field(None, min_length=8)
    role: Literal["manager", "kitchen", "staff"]


class CandidatePatch(BaseModel):
    category: str | None = Field(None, max_length=120)
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=1200)
    price_minor: int | None = Field(None, ge=0, le=10_000_000)
    review_state: Literal["pending", "approved", "rejected"] | None = None


class AnalyticsIn(BaseModel):
    restaurant_slug: str
    event_type: Literal["menu_view", "dish_view", "rec_impression", "rec_click", "add_to_cart", "chat_question"]
    item_id: str | None = None


class ReorderIn(BaseModel):
    kind: str = Field(pattern="^(categories|items)$")
    ids: list[str] = Field(min_length=1, max_length=500)
    category_id: str | None = None


class RefundIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=600)
