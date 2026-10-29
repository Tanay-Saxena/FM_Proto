"""Receipt creation and notification delivery (separate lifecycle from payment/order state)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from ..defaults import merged_config
from ..models import NotificationJob, Payment, Receipt, Restaurant, TableSession
from ..providers.messaging import PermanentError, TransientError, get_provider
from ..security import public_token
from .audit import audit

BACKOFF_SECONDS = [30, 120, 600, 1800]
MAX_ATTEMPTS = 5


def create_receipt(db: Session, session: TableSession, payment: Payment, bill_data: dict) -> Receipt:
    existing = db.query(Receipt).filter(Receipt.payment_id == payment.id).first()
    if existing:
        return existing
    r = db.get(Restaurant, session.restaurant_id)
    seq = db.query(Receipt).filter(Receipt.restaurant_id == r.id).count() + 1
    prefix = "".join(c for c in r.slug.upper() if c.isalnum())[:3] or "RCT"
    receipt = Receipt(
        restaurant_id=r.id,
        session_id=session.id,
        payment_id=payment.id,
        token=public_token(24),
        number=f"{prefix}-{seq:05d}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().receipt_ttl_days),
        data={
            "restaurant": {"name": r.name, "tagline": r.tagline, "currency": r.currency, "timezone": r.timezone, "is_demo": r.is_demo},
            "table": session.table.label if session.table else "",
            "guest_first_name": (session.contact_name or "").split(" ")[0],
            "bill": bill_data,
            "payment": {"provider": payment.provider, "reference": payment.provider_ref, "paid_at": (payment.paid_at or datetime.now(timezone.utc)).isoformat(), "simulated": payment.simulated},
        },
    )
    db.add(receipt)
    db.flush()
    queue_notifications(db, receipt, session)
    audit(db, "system", "receipt.created", r.id, "receipt", receipt.id, {"number": receipt.number})
    return receipt


def queue_notifications(db: Session, receipt: Receipt, session: TableSession):
    now = datetime.now(timezone.utc)
    for channel, recipient in (("sms", session.contact_phone), ("email", session.contact_email)):
        if not recipient:
            continue
        if db.query(NotificationJob).filter(NotificationJob.receipt_id == receipt.id, NotificationJob.channel == channel).first():
            continue
        prov = get_provider(channel)
        db.add(NotificationJob(restaurant_id=receipt.restaurant_id, receipt_id=receipt.id, channel=channel, recipient=recipient, state="queued", next_attempt_at=now, provider=prov.name, simulated=prov.simulated))


def _render(template: str, **values) -> str:
    for k, v in values.items():  # plain replace: templates can't execute format-string tricks
        template = template.replace("{" + k + "}", v)
    return template


def deliver(db: Session, job: NotificationJob) -> NotificationJob:
    if job.state == "sent":
        return job  # idempotent: never resend
    receipt = db.get(Receipt, job.receipt_id)
    restaurant = db.get(Restaurant, job.restaurant_id)
    cfg = merged_config(restaurant.config)["templates"]
    link = f"{get_settings().public_base_url}/receipt/{receipt.token}"
    body = _render(cfg["sms"] if job.channel == "sms" else cfg["email_body"], restaurant=restaurant.name, link=link)
    subject = _render(cfg["email_subject"], restaurant=restaurant.name, link=link) if job.channel == "email" else None
    job.state = "sending"
    job.attempts += 1
    db.flush()
    try:
        ref = get_provider(job.channel).send(job.recipient, subject, body)
        job.state, job.provider_ref, job.last_error = "sent", ref, None
        job.sent_at = datetime.now(timezone.utc)
        job.next_attempt_at = None
    except PermanentError as e:
        job.state, job.last_error, job.next_attempt_at = "failed", str(e)[:300], None
    except TransientError as e:
        job.last_error = str(e)[:300]
        if job.attempts >= MAX_ATTEMPTS:
            job.state, job.next_attempt_at = "failed", None
        else:
            job.state = "retry_scheduled"
            job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_SECONDS[min(job.attempts - 1, len(BACKOFF_SECONDS) - 1)])
    db.commit()
    return job


def process_due_jobs(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    jobs = db.query(NotificationJob).filter(NotificationJob.state.in_(["queued", "retry_scheduled"]), NotificationJob.next_attempt_at <= now).all()
    for j in jobs:
        deliver(db, j)
    return len(jobs)


def mask(recipient: str) -> str:
    if "@" in recipient:
        name, _, dom = recipient.partition("@")
        return f"{name[:1]}***@{dom}"
    return f"{recipient[:3]}•••{recipient[-2:]}" if len(recipient) > 6 else "•••"
