import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import get_settings
from .db import Base, SessionLocal, engine
from .routers import admin, auth, public, webhooks
from .services.errors import DomainError
from .services.receipts import process_due_jobs

settings = get_settings()
logging.basicConfig(level=logging.INFO, format='{"t":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
log = logging.getLogger("foodmania")


async def _worker():
    """In-process notification worker (retries with backoff). Swap for a real queue in production."""
    tick = 0
    while True:
        try:
            db = SessionLocal()
            try:
                await asyncio.get_event_loop().run_in_executor(None, process_due_jobs, db)
                tick += 1
                if tick % 720 == 1:  # roughly hourly: enforce the contact-retention window
                    from .retention import purge_contacts
                    await asyncio.get_event_loop().run_in_executor(None, purge_contacts, db)
            finally:
                db.close()
        except Exception:
            log.exception("worker_error")
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.secret_key == "dev-only-change-me" and not settings.demo_mode:
        raise RuntimeError("SECRET_KEY must be set when DEMO_MODE is off")
    Base.metadata.create_all(engine)  # dev convenience; Alembic is the migration path (docs/RUNBOOK.md)
    task = asyncio.create_task(_worker()) if settings.run_background_worker else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="FoodMania API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


_ALLOWED_ORIGINS = {o.strip().rstrip("/") for o in settings.cors_origins.split(",")} | {settings.public_base_url.rstrip("/")}


@app.middleware("http")
async def origin_check(request: Request, call_next):
    """CSRF defence for the cookie session: a browser sending an unsafe request from a foreign Origin is refused.
    Requests without an Origin header (server-to-server, webhooks, curl) are unaffected."""
    origin = request.headers.get("origin")
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and origin and origin.rstrip("/") not in _ALLOWED_ORIGINS and not request.url.path.startswith("/api/v1/webhooks"):
        return _err(403, "bad_origin", "This request came from an origin that isn't allowed.")
    return await call_next(request)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["cache-control"] = "no-store" if request.url.path.startswith("/api") and not request.url.path.startswith("/api/v1/media/") else response.headers.get("cache-control", "")
    log.info("%s %s %s %dms rid=%s", request.method, request.url.path, response.status_code, (time.perf_counter() - start) * 1000, rid)
    return response


def _err(status: int, code: str, message: str, detail=None):
    return JSONResponse({"error": {"code": code, "message": message, "detail": detail}}, status_code=status)


@app.exception_handler(DomainError)
async def domain_error(_, e: DomainError):
    return _err(e.status, e.code, e.message, e.detail)


@app.exception_handler(HTTPException)
async def http_error(_, e: HTTPException):
    return _err(e.status_code, "http_error", str(e.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_, e: RequestValidationError):
    fields = [{"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]} for err in e.errors()]
    first = fields[0] if fields else {"field": "", "message": "Invalid request"}
    return _err(422, "validation_error", f"{first['field'] or 'Request'}: {first['message']}".strip(), fields)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return {"status": "ready", "demo_mode": settings.demo_mode, "payment_provider": settings.payment_provider}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)


for r in (public.router, auth.router, admin.router, webhooks.router):
    app.include_router(r, prefix="/api/v1")
