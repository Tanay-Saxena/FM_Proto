import threading
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()
IS_SQLITE = settings.database_url.startswith("sqlite")

_kwargs = {"connect_args": {"check_same_thread": False, "timeout": 30}} if IS_SQLITE else {"pool_pre_ping": True}
engine = create_engine(settings.database_url, **_kwargs)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# SQLite has no row locks; serialise critical write sections in-process. On PostgreSQL the same
# sections use SELECT ... FOR UPDATE (see `lock_row`).
_write_lock = threading.RLock()


@contextmanager
def critical_section():
    if IS_SQLITE:
        with _write_lock:
            yield
    else:
        yield


def lock_row(db, model, pk):
    """Load a row for update. FOR UPDATE on Postgres; no-op on SQLite (guarded by critical_section)."""
    q = db.query(model).filter(model.id == pk).populate_existing()  # never trust a cached copy
    if not IS_SQLITE:
        q = q.with_for_update()
    return q.one()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
