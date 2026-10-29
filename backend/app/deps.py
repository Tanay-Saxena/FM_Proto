"""Authentication & authorization dependencies. Authorization is enforced here, in the backend."""
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Membership, Restaurant, User
from .security import read_token

COOKIE = "fm_session"

ROLE_PERMS: dict[str, set[str]] = {
    "owner": {"*"},
    "manager": {
        "menu.view", "menu.edit", "menu.publish", "availability.edit", "recommendations.edit", "tables.manage",
        "orders.view", "orders.transition", "orders.cancel", "sessions.manage", "payments.view", "notifications.retry",
        "analytics.view", "tables.view", "sessions.view", "kitchen.view", "menu.availability", "uploads.manage", "settings.view", "staff.view", "pos.sync",
    },
    "kitchen": {"orders.view", "orders.transition", "kitchen.view", "menu.view"},
    "staff": {"orders.view", "menu.view", "menu.availability", "tables.view", "sessions.view"},
}


def has_perm(role: str, perm: str) -> bool:
    perms = ROLE_PERMS.get(role, set())
    return "*" in perms or perm in perms


def demo_now(request: Request) -> datetime:
    """Demo clock: honoured only when DEMO_MODE is on. Production ignores the header."""
    raw = request.headers.get("x-demo-time")
    if raw and get_settings().demo_mode:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo:
                return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    data = read_token(token) if token else None
    if not data:
        raise HTTPException(401, "Sign in to continue")
    user = db.get(User, data["uid"])
    if not user or not user.active:
        raise HTTPException(401, "Sign in to continue")
    return user


def platform_admin(user: User = Depends(current_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(403, "Platform administrators only")
    return user


class Access:
    def __init__(self, user: User, restaurant: Restaurant, role: str):
        self.user, self.restaurant, self.role = user, restaurant, role

    @property
    def actor(self) -> str:
        return f"{self.user.email} ({self.role})"

    def require(self, perm: str):
        if not has_perm(self.role, perm):
            raise HTTPException(403, "Your role doesn't allow this action")
        return self


def access_for(db: Session, user: User, restaurant_id: str, perm: str) -> Access:
    """Resolve membership for a restaurant. Non-members get 404 so tenants can't probe each other."""
    r = db.get(Restaurant, restaurant_id)
    m = (
        db.query(Membership).filter(Membership.user_id == user.id, Membership.restaurant_id == restaurant_id).first()
        if r
        else None
    )
    if not r or not m:
        raise HTTPException(404, "Restaurant not found")
    return Access(user, r, m.role).require(perm)


def require(perm: str):
    """Dependency factory for routes with a `restaurant_id` path parameter."""

    def dep(restaurant_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Access:
        return access_for(db, user, restaurant_id, perm)

    return dep
