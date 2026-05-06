"""Email channel adapter — IMAP polling for incoming, SMTP for outgoing."""
from typing import Callable, List, Optional

from cuga.personal.gateway.base import ChannelAdapter, DeliveryTarget


class EmailAdapter(ChannelAdapter):
    """
    Email adapter: polls IMAP for incoming messages, uses SMTP for replies.
    Useful for async workflows and scheduled report delivery.

    Thread tracking uses email Message-ID / References headers.
    """

    platform = "email"

    def __init__(
        self,
        email_address: str,
        imap_server: str,
        smtp_server: str,
        password: str,
        poll_interval: int = 60,
    ):
        self.email_address = email_address
        self.imap_server = imap_server
        self.smtp_server = smtp_server
        self._password = password
        self.poll_interval = poll_interval
        self._running = False
        self._on_message: Optional[Callable] = None

    async def start(self, on_message: Callable) -> None:
        self._on_message = on_message
        self._running = True
        # TODO: Implement IMAP polling loop (Phase 2)
        raise NotImplementedError("Email adapter polling not yet implemented")

    async def stop(self) -> None:
        self._running = False

    async def send(self, target: DeliveryTarget, text: str, files: Optional[List[dict]] = None) -> None:
        # TODO: Implement SMTP send (Phase 2)
        raise NotImplementedError("Email adapter send not yet implemented")

    async def get_user_context(self, user_id: str) -> dict:
        return {"user_id": user_id, "email": user_id, "platform": self.platform}
