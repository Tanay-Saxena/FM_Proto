from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import sessions as sess

router = APIRouter()


@router.post("/webhooks/payments/{provider}")
async def payment_webhook(provider: str, request: Request, db: Session = Depends(get_db)):
    """Signature-verified, idempotent. The only route that can mark a bill paid."""
    body = await request.body()
    return sess.handle_payment_event(db, provider, request.headers, body)
