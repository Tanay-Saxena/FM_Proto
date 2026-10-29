"""SMS / email provider adapters. Only logging mocks ship; mock sends are marked simulated=True and
the UI must never present them as externally delivered."""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

log = logging.getLogger("foodmania.notify")


class TransientError(Exception):
    """Retryable provider failure."""


class PermanentError(Exception):
    """Do not retry (bad recipient etc.)."""


class MessageProvider(Protocol):
    name: str
    simulated: bool

    def send(self, recipient: str, subject: str | None, body: str) -> str: ...


class MockMessageProvider:
    """Logs instead of sending. `fail_next(n)` and recipients containing 'fail' exist for tests/demo."""

    simulated = True

    def __init__(self, channel: str):
        self.channel = channel
        self.name = f"mock-{channel}"
        self._fail_next = 0

    def fail_next(self, n: int = 1):
        self._fail_next = n

    def send(self, recipient, subject, body) -> str:
        if "permfail" in recipient:
            raise PermanentError("recipient rejected (simulated)")
        if self._fail_next > 0 or "fail" in recipient:
            self._fail_next = max(0, self._fail_next - 1)
            raise TransientError("provider unavailable (simulated)")
        # Never log full contact details or message content.
        log.info("SIMULATED %s to %s*** (not delivered)", self.channel, recipient[:3])
        return f"sim_{uuid.uuid4().hex[:12]}"


SMS = MockMessageProvider("sms")
EMAIL = MockMessageProvider("email")


def get_provider(channel: str) -> MockMessageProvider:
    return SMS if channel == "sms" else EMAIL
