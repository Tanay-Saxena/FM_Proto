"""Privacy retention: guest contact details are only needed to serve the table and send the receipt.
Run `python -m app.retention` (cron) or let the API worker call purge_contacts() hourly."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .config import get_settings
from .models import TableSession
from .services.audit import audit


def purge_contacts(db: Session, days: int | None = None) -> int:
    days = days if days is not None else get_settings().contact_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(TableSession).filter(TableSession.closed_at.isnot(None), TableSession.closed_at < cutoff, TableSession.contact_purged_at.is_(None),
                                         (TableSession.contact_name.isnot(None)) | (TableSession.contact_phone.isnot(None)) | (TableSession.contact_email.isnot(None))).all()
    for s in rows:
        s.contact_name = s.contact_phone = s.contact_email = None
        s.contact_purged_at = datetime.now(timezone.utc)
        audit(db, "system", "contact.purged", s.restaurant_id, "table_session", s.id, {"retention_days": days})
    db.commit()
    return len(rows)


if __name__ == "__main__":
    from .db import SessionLocal
    with SessionLocal() as db:
        print(f"purged contact details from {purge_contacts(db)} sessions")
