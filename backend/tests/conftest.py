import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="fm-test-")
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/test.db", RUN_BACKGROUND_WORKER="false", DEMO_MODE="true", STORAGE_DIR=f"{_tmp}/storage", SECRET_KEY="test-secret", PAYMENT_WEBHOOK_SECRET="test-webhook-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import seed as seed_mod  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app import ratelimit  # noqa: E402

# Wednesday 2026-10-28 13:00 IST (07:30Z): inside Spice Route kitchen hours and the lunch thali window.
LUNCH = "2026-10-28T07:30:00Z"


@pytest.fixture(scope="session", autouse=True)
def _seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_mod.seed(db)
    db.close()


@pytest.fixture(autouse=True)
def _reset_limits():
    ratelimit.reset()


@pytest.fixture()
def db():
    d = SessionLocal()
    yield d
    d.close()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client, email, password="demo1234"):
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture(scope="session")
def owner(client):
    return login(client, "owner@spiceroute.demo")


@pytest.fixture(scope="session")
def rid(client, owner):
    return next(m["restaurant_id"] for m in owner.get("/api/v1/auth/me").json()["memberships"])


def menu_items(client, slug="spice-route", at=LUNCH):
    m = client.get(f"/api/v1/restaurants/{slug}/menu", headers={"x-demo-time": at}).json()
    return {i["name"]: i for c in m["categories"] for i in c["items"]}


def new_table_session(owner, rid, client, label):
    t = owner.post(f"/api/v1/restaurants/{rid}/tables", json={"label": label}).json()
    qr = t["qr_url"].rsplit("/", 1)[1]
    tok = client.post(f"/api/v1/qr/{qr}/session").json()["session_token"]
    return tok


def give_contact(client, tok):
    r = client.post(f"/api/v1/table-sessions/{tok}/contact", json={"name": "Test Guest", "phone": "+919876500000", "email": "guest@example.com", "consent": True})
    assert r.status_code == 200, r.text


_n = [0]


def place(client, tok, lines, at=LUNCH, key=None):
    _n[0] += 1
    return client.post(f"/api/v1/table-sessions/{tok}/orders", headers={"x-demo-time": at}, json={"idempotency_key": key or f"key-test-{_n[0]:06d}", "lines": [{"item_id": i, "quantity": q} for i, q in lines]})
