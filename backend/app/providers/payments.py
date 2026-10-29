"""Payment provider adapter. Order/bill logic never imports a concrete provider.

Only MockPaymentProvider ships. A real India UPI-capable gateway (Razorpay / Cashfree / PhonePe PG …)
is a TODO that needs merchant onboarding + sandbox credentials — see docs/DECISIONS.md D-002.
The webhook verification contract is real: events are HMAC-signed and verified before any state change.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Mapping, Protocol

from ..config import get_settings


class WebhookVerificationError(Exception):
    pass


class PaymentProvider(Protocol):
    name: str
    simulated: bool

    def create_payment(self, *, payment_id: str, amount_minor: int, currency: str, reference: str) -> dict: ...
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> dict: ...
    def refund(self, *, provider_ref: str, amount_minor: int, currency: str, reason: str) -> dict: ...


class MockPaymentProvider:
    name = "mock"
    simulated = True
    signature_header = "x-mock-signature"

    def _secret(self) -> bytes:
        return get_settings().payment_webhook_secret.encode()

    def sign(self, body: bytes) -> str:
        return hmac.new(self._secret(), body, hashlib.sha256).hexdigest()

    def create_payment(self, *, payment_id, amount_minor, currency, reference) -> dict:
        return {"provider_ref": f"mockpay_{uuid.uuid4().hex[:20]}", "simulated": True}

    def refund(self, *, provider_ref, amount_minor, currency, reason) -> dict:
        # A real gateway call (and its failure modes) goes here; the mock always succeeds, clearly simulated.
        return {"refund_ref": f"mockrefund_{uuid.uuid4().hex[:18]}", "simulated": True}

    def verify_webhook(self, headers, body) -> dict:
        sig = headers.get(self.signature_header) or headers.get(self.signature_header.title())
        if not sig or not hmac.compare_digest(sig, self.sign(body)):
            raise WebhookVerificationError("invalid signature")
        try:
            event = json.loads(body)
            for k in ("event_id", "type", "provider_ref"):
                if not isinstance(event.get(k), str):
                    raise ValueError(k)
            return event
        except (ValueError, TypeError) as e:
            raise WebhookVerificationError(f"malformed event: {e}")

    def build_event(self, *, provider_ref: str, amount_minor: int, currency: str, outcome: str, event_id: str | None = None) -> tuple[bytes, str]:
        """Used only by the simulated checkout to emulate a provider calling our webhook."""
        etype = {"success": "payment.succeeded", "failure": "payment.failed", "cancel": "payment.cancelled"}[outcome]
        body = json.dumps(
            {"event_id": event_id or f"evt_{uuid.uuid4().hex[:16]}", "type": etype, "provider_ref": provider_ref, "amount_minor": amount_minor, "currency": currency},
            separators=(",", ":"),
        ).encode()
        return body, self.sign(body)


_PROVIDERS = {"mock": MockPaymentProvider()}


def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or get_settings().payment_provider
    if name not in _PROVIDERS:
        raise KeyError(f"payment provider '{name}' is not configured")
    return _PROVIDERS[name]
