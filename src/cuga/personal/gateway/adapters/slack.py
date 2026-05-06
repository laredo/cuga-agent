"""Slack channel adapter using slack_bolt (async)."""
import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional

from cuga.personal.gateway.base import ChannelAdapter, DeliveryTarget, MessageEvent, MessageType


class SlackAdapter(ChannelAdapter):
    """
    Slack adapter built on slack_bolt AsyncApp.

    Handles: DMs, channel mentions, slash commands, file uploads, thread replies.
    Requires: SLACK_BOT_TOKEN, SLACK_APP_TOKEN (Socket Mode) or SLACK_SIGNING_SECRET (HTTP).

    slack_bolt is an optional dependency — import errors surface only when the adapter
    is actually instantiated.
    """

    platform = "slack"

    def __init__(self, bot_token: str, app_token: Optional[str] = None, signing_secret: Optional[str] = None):
        try:
            from slack_bolt.async_app import AsyncApp
        except ImportError as e:
            raise ImportError(
                "slack_bolt is required for SlackAdapter. "
                "Install with: pip install cuga[personal]"
            ) from e

        self._app = AsyncApp(token=bot_token, signing_secret=signing_secret)
        self._client = self._app.client
        self._app_token = app_token
        self._on_message: Optional[Callable] = None
        self._register_handlers()

    def _register_handlers(self):
        @self._app.event("message")
        async def handle_message(event, say):
            if self._on_message:
                msg_event = self.parse_event(event)
                await self._on_message(msg_event)

    async def start(self, on_message: Callable) -> None:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._on_message = on_message
        handler = AsyncSocketModeHandler(self._app, self._app_token)
        await handler.start_async()

    async def stop(self) -> None:
        pass

    async def send(self, target: DeliveryTarget, text: str, files: Optional[List[dict]] = None) -> None:
        kwargs = {"channel": target.channel_id, "text": text}
        if target.thread_id:
            kwargs["thread_ts"] = target.thread_id
        await self._client.chat_postMessage(**kwargs)

    async def get_user_context(self, user_id: str) -> dict:
        result = await self._client.users_info(user=user_id)
        user = result.get("user", {})
        return {
            "user_id": user_id,
            "display_name": user.get("profile", {}).get("display_name", ""),
            "email": user.get("profile", {}).get("email", ""),
            "platform": self.platform,
        }

    # ------------------------------------------------------------------
    # Static helpers (testable without a live Slack connection)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_event(raw: dict) -> MessageEvent:
        """Convert a raw Slack event dict into a platform-agnostic MessageEvent."""
        files = raw.get("files", [])
        has_files = bool(files)
        text = raw.get("text", "")
        stripped = text.strip()

        if stripped.startswith("/"):
            msg_type = MessageType.COMMAND
        elif has_files:
            msg_type = MessageType.FILE
        else:
            msg_type = MessageType.TEXT

        ts = raw.get("ts", "0")
        try:
            timestamp = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except (ValueError, TypeError):
            timestamp = datetime.now(timezone.utc)

        return MessageEvent(
            id=raw.get("event_ts", str(uuid.uuid4())),
            channel_id=raw.get("channel", ""),
            user_id=raw.get("user", ""),
            platform="slack",
            type=msg_type,
            text=stripped,
            files=[{"name": f.get("name", ""), "url": f.get("url_private", "")} for f in files],
            thread_id=raw.get("thread_ts"),
            timestamp=timestamp,
            metadata={"ts": ts},
        )
