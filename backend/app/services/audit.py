from ..models import AuditLog


def audit(db, actor: str, action: str, restaurant_id: str | None = None, resource_type: str = "", resource_id: str = "", detail: dict | None = None):
    db.add(AuditLog(actor=actor, action=action, restaurant_id=restaurant_id, resource_type=resource_type, resource_id=resource_id, detail=detail or {}))
