"""SQLAlchemy models. Money is always integer minor units (paise). IDs are UUID strings."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


# ───────────────────────────── Tenancy & access ─────────────────────────────
class Restaurant(Base, TimestampMixin):
    __tablename__ = "restaurants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    tagline: Mapped[str] = mapped_column(String(240), default="")
    venue_type: Mapped[str] = mapped_column(String(40), default="restaurant")
    cuisine: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | suspended
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    locale: Mapped[str] = mapped_column(String(16), default="en-IN")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Validated design tokens only (see schemas.ThemeTokens). Never raw CSS/HTML.
    theme: Mapped[dict] = mapped_column(JSON, default=dict)
    # features, tax/service, ordering policy, notification templates (see schemas.RestaurantConfig)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Base, TimestampMixin):
    __tablename__ = "restaurant_memberships"
    __table_args__ = (UniqueConstraint("user_id", "restaurant_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # owner | manager | kitchen | staff
    user: Mapped[User] = relationship()


class RestaurantTable(Base, TimestampMixin):
    __tablename__ = "restaurant_tables"
    __table_args__ = (UniqueConstraint("restaurant_id", "label"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(40))
    zone: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | disabled


class QrCode(Base, TimestampMixin):
    __tablename__ = "qr_codes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    table_id: Mapped[str] = mapped_column(ForeignKey("restaurant_tables.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ───────────────────────────── Menus ─────────────────────────────
class Menu(Base, TimestampMixin):
    __tablename__ = "menus"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Main menu")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | published | archived
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    categories: Mapped[list["Category"]] = relationship(back_populates="menu", cascade="all, delete-orphan", order_by="Category.sort")


class Category(Base):
    __tablename__ = "menu_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    menu_id: Mapped[str] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"), index=True)
    stable_key: Mapped[str] = mapped_column(String(36), default=uid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(240), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    menu: Mapped[Menu] = relationship(back_populates="categories")
    items: Mapped[list["Item"]] = relationship(back_populates="category", cascade="all, delete-orphan", order_by="Item.sort")


class Item(Base, TimestampMixin):
    __tablename__ = "menu_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    menu_id: Mapped[str] = mapped_column(ForeignKey("menus.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("menu_categories.id", ondelete="CASCADE"), index=True)
    # Stable identity across menu versions so rules/analytics keep pointing at "the same dish".
    stable_key: Mapped[str] = mapped_column(String(36), default=uid, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    price_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    state: Mapped[str] = mapped_column(String(20), default="available")  # available|paused|sold_out|hidden
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    stock_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # [{key, value, source: restaurant_confirmed|source_derived|ai_suggested, verified: bool}]
    attributes: Mapped[list] = mapped_column(JSON, default=list)
    # {verified: bool, list: [str]} — an unverified/empty list never means "free of".
    allergens: Mapped[dict] = mapped_column(JSON, default=lambda: {"verified": False, "list": []})
    ingredients: Mapped[dict] = mapped_column(JSON, default=lambda: {"verified": False, "list": []})
    image: Mapped[dict] = mapped_column(JSON, default=dict)  # {kind, hue, url?, provenance}
    # [{id, name, min, max, options:[{id, name, price_minor}]}]
    modifier_groups: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[Category] = relationship(back_populates="items")


class AvailabilityRule(Base, TimestampMixin):
    """kind: weekly (days + HH:MM window, optional season dates) | date_exception (a date + effect)
    | season (date range only). effect: allow (open in this window) | block (closed)."""

    __tablename__ = "availability_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # restaurant | category | item
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # item: stable_key; category: name key
    kind: Mapped[str] = mapped_column(String(20))
    effect: Mapped[str] = mapped_column(String(10), default="allow")
    label: Mapped[str] = mapped_column(String(80), default="")
    days: Mapped[list] = mapped_column(JSON, default=list)  # 0=Mon..6=Sun; empty = every day
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD, local
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RecommendationRule(Base, TimestampMixin):
    __tablename__ = "recommendation_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20))  # item | category
    target_id: Mapped[str] = mapped_column(String(36))  # item: stable_key; category: category name
    weight: Mapped[int] = mapped_column(Integer, default=0)  # -5..+5, bounded
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str] = mapped_column(String(60), default="")
    allow_in_recommendations: Mapped[bool] = mapped_column(Boolean, default=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# ───────────────────────────── Ingestion ─────────────────────────────
class MenuUpload(Base, TimestampMixin):
    __tablename__ = "menu_uploads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(60))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class IngestionJob(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    upload_id: Mapped[str] = mapped_column(ForeignKey("menu_uploads.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|processing|review|failed|approved
    method: Mapped[str] = mapped_column(String(20), default="")  # pdf_text | ocr
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_menu_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    upload: Mapped[MenuUpload] = relationship()


class IngestionCandidate(Base):
    __tablename__ = "ingestion_candidates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(120), default="")
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(default=1.0)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[dict] = mapped_column(JSON, default=dict)  # {page, line, raw}
    review_state: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    sort: Mapped[int] = mapped_column(Integer, default=0)


# ───────────────────────────── Sessions & ordering ─────────────────────────────
class TableSession(Base, TimestampMixin):
    __tablename__ = "table_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    table_id: Mapped[str] = mapped_column(ForeignKey("restaurant_tables.id", ondelete="CASCADE"), index=True)
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(20), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_seq: Mapped[int] = mapped_column(Integer, default=0)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    table: Mapped[RestaurantTable] = relationship()
    orders: Mapped[list["Order"]] = relationship(back_populates="session", order_by="Order.ticket_seq")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "number"),
        UniqueConstraint("session_id", "ticket_seq"),
        UniqueConstraint("session_id", "idempotency_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(ForeignKey("restaurants.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("table_sessions.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    ticket_seq: Mapped[int] = mapped_column(Integer)  # 1 = original, 2+ = add-on
    ticket_type: Mapped[str] = mapped_column(String(10))  # original | addon
    state: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    notes: Mapped[str] = mapped_column(String(300), default="")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    reject_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session: Mapped[TableSession] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    events: Mapped[list["OrderStatusEvent"]] = relationship(cascade="all, delete-orphan", order_by="OrderStatusEvent.at")

    @property
    def label(self) -> str:
        return chr(64 + self.ticket_seq) if self.ticket_seq <= 26 else str(self.ticket_seq)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    stable_key: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(160))
    unit_price_minor: Mapped[int] = mapped_column(Integer)  # includes modifier deltas
    quantity: Mapped[int] = mapped_column(Integer)
    modifiers: Mapped[list] = mapped_column(JSON, default=list)  # [{group, name, price_minor}]
    notes: Mapped[str] = mapped_column(String(200), default="")
    line_total_minor: Mapped[int] = mapped_column(Integer)
    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    from_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_state: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(80), default="system")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    seq: Mapped[int] = mapped_column(Integer, default=0)  # cursor for kitchen polling


# ───────────────────────────── Billing, payments, receipts ─────────────────────────────
class Bill(Base, TimestampMixin):
    __tablename__ = "bills"
    __table_args__ = (UniqueConstraint("session_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("table_sessions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | superseded | paid
    data: Mapped[dict] = mapped_column(JSON)  # full computed bill snapshot
    total_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("table_sessions.id", ondelete="CASCADE"), index=True)
    bill_id: Mapped[str] = mapped_column(ForeignKey("bills.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    provider_ref: Mapped[str] = mapped_column(String(120), unique=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(20), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_minor: Mapped[int] = mapped_column(Integer, default=0)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    refund_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)


class PaymentEvent(Base, TimestampMixin):
    __tablename__ = "payment_events"
    __table_args__ = (UniqueConstraint("provider", "event_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider: Mapped[str] = mapped_column(String(30))
    event_id: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(40))
    payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    restaurant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(40), default="")  # applied | duplicate | amount_mismatch | ...
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Receipt(Base, TimestampMixin):
    __tablename__ = "receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("table_sessions.id", ondelete="CASCADE"), index=True)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id", ondelete="CASCADE"), unique=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    number: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Review(Base, TimestampMixin):
    """One guest review per paid receipt. Only someone holding the receipt link can leave it."""
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(String(600), default="")
    guest_first_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)  # left on a sample restaurant


class NotificationJob(Base, TimestampMixin):
    __tablename__ = "notification_jobs"
    __table_args__ = (UniqueConstraint("receipt_id", "channel"), Index("ix_notif_due", "state", "next_attempt_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(10))  # sms | email
    recipient: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(20), default="queued")  # queued|sending|sent|failed|retry_scheduled
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="mock")
    provider_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationEvent(Base, TimestampMixin):
    __tablename__ = "integration_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(30))
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


# ───────────────────────────── Supporting ─────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(40), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    restaurant_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    item_key: Mapped[str | None] = mapped_column(String(36), nullable=True)
    session_ref: Mapped[str | None] = mapped_column(String(16), nullable=True)  # hashed, not the token
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
