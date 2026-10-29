from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import COOKIE, current_user
from ..models import Membership, Restaurant, User
from ..ratelimit import limit
from ..schemas import LoginIn
from ..security import sign_token, verify_password
from ..services.audit import audit
from ..services.errors import DomainError

router = APIRouter(prefix="/auth")


def user_view(db: Session, u: User) -> dict:
    rows = db.query(Membership, Restaurant).join(Restaurant, Restaurant.id == Membership.restaurant_id).filter(Membership.user_id == u.id).all()
    return {"id": u.id, "email": u.email, "name": u.name, "is_platform_admin": u.is_platform_admin,
            "memberships": [{"restaurant_id": r.id, "slug": r.slug, "name": r.name, "role": m.role} for m, r in rows]}


@router.post("/login", dependencies=[Depends(limit("login", 10, 60))])
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not u or not u.active or not verify_password(body.password, u.password_hash):
        raise DomainError("bad_credentials", "Email or password is incorrect.", 401)
    s = get_settings()
    ttl = s.session_ttl_hours * 3600
    response.set_cookie(COOKIE, sign_token({"uid": u.id}, ttl), max_age=ttl, httponly=True, samesite="lax", secure=s.cookie_secure, path="/")
    audit(db, u.email, "auth.login")
    db.commit()
    return user_view(db, u)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_view(db, u)
