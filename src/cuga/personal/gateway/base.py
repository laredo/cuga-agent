"""Gateway base: platform-agnostic message models and channel adapter ABC."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class MessageType(str, Enum):
    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    COMMAND = "command"


class MessageEvent(BaseModel):
    """Platform-agnostic inbound message."""

    id: str
    channel_id: str
    user_id: str
    platform: str  # "slack" | "cli" | "email" | ...
    type: MessageType
    text: str
    files: List[dict] = []
    thread_id: Optional[str] = None
    timestamp: datetime
    metadata: dict = {}


class DeliveryTarget(BaseModel):
    """Where to send a response."""

    platform: str
    channel_id: str
    thread_id: Optional[str] = None
    user_id: Optional[str] = None


class ChannelAdapter(ABC):
    """Abstract base for all channel integrations."""

    @abstractmethod
    async def start(self, on_message) -> None:
        """Start listening. Calls on_message(MessageEvent) for each inbound message."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop listening and clean up."""

    @abstractmethod
    async def send(self, target: DeliveryTarget, text: str, files: Optional[List[dict]] = None) -> None:
        """Deliver a response to the given target."""

    @abstractmethod
    async def get_user_context(self, user_id: str) -> dict:
        """Return platform-specific user profile / auth context."""
