"""Slack channel adapter using slack_bolt (async)."""

import uuid
from datetime import datetime, timezone
from typing import Callable, List, Optional

from cuga.personal.gateway.base import ChannelAdapter, DeliveryTarget, MessageEvent, MessageType


class SlackAdapter(ChannelAdapter):
    """
    Slack adapter built on slack_bolt AsyncApp.

    Handles: DMs, channel @mentions, slash commands, thread replies.
    Uses Socket Mode (SLACK_APP_TOKEN) — no public URL required.

    Filters out bot messages and message_changed/message_deleted subtypes
    to avoid echo loops.
    """

    platform = "slack"

    def __init__(
        self, 
        bot_token: str, 
        app_token: Optional[str] = None, 
        signing_secret: Optional[str] = None,
        force_threaded_replies: bool = True,
        unfurl_links: bool = False,
        unfurl_media: bool = False,
    ):
        try:
            from slack_bolt.async_app import AsyncApp
        except ImportError as e:
            raise ImportError(
                "slack_bolt is required for SlackAdapter. Install with: pip install cuga[personal]"
            ) from e

        self._app = AsyncApp(token=bot_token, signing_secret=signing_secret)
        self._client = self._app.client
        self._app_token = app_token
        self._force_threaded_replies = force_threaded_replies
        self._unfurl_links = unfurl_links
        self._unfurl_media = unfurl_media
        self._on_message: Optional[Callable] = None
        self._register_handlers()

    def _register_handlers(self):
        @self._app.event("message")
        async def handle_message(event, say):
            # Ignore bot messages and system subtypes (edits, deletes, joins)
            if event.get("bot_id") or event.get("subtype"):
                return
            if self._on_message:
                msg_event = self.parse_event(event, force_threaded=self._force_threaded_replies)
                if msg_event.text:
                    await self._on_message(msg_event)

        @self._app.event("app_mention")
        async def handle_mention(event, say):
            # Strip the @bot mention prefix before dispatching
            text = event.get("text", "")
            # Remove <@BOTID> prefix
            import re

            text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
            event = {**event, "text": text}
            if self._on_message and text:
                msg_event = self.parse_event(event, force_threaded=self._force_threaded_replies)
                await self._on_message(msg_event)

    async def start(self, on_message: Callable) -> None:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._on_message = on_message
        handler = AsyncSocketModeHandler(self._app, self._app_token)
        await handler.start_async()

    async def stop(self) -> None:
        pass

    async def send(self, target: DeliveryTarget, text: str, files: Optional[List[dict]] = None) -> None:
        kwargs: dict = {
            "channel": target.channel_id, 
            "text": text,
            "unfurl_links": self._unfurl_links,
            "unfurl_media": self._unfurl_media
        }
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
    def parse_event(raw: dict, force_threaded: bool = False) -> MessageEvent:
        """Convert a raw Slack event dict into a platform-agnostic MessageEvent."""
        files = raw.get("files", [])
        text = raw.get("text", "").strip()

        if text.startswith("/"):
            msg_type = MessageType.COMMAND
        elif files:
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
            text=text,
            files=[{"name": f.get("name", ""), "url": f.get("url_private", "")} for f in files],
            thread_id=raw.get("thread_ts") or (raw.get("ts") if force_threaded else None),
            timestamp=timestamp,
            metadata={"ts": ts},
        )
