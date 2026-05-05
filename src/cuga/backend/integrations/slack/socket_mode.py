"""Socket Mode handler for Slack integration

Enables Slack integration without webhooks or public URLs.
Perfect for development and testing.
"""

import os
import asyncio
from typing import Optional
from loguru import logger

from cuga.backend.events.queue import EventQueue
from cuga.backend.events.models import Event, EventType, EventSource


class SocketModeHandler:
    """Handles Slack Socket Mode connection and event routing"""
    
    def __init__(self, event_queue: EventQueue, bot_token: str, app_token: str):
        """Initialize Socket Mode handler
        
        Args:
            event_queue: Event queue for enqueueing Slack events
            bot_token: Slack bot token (xoxb-)
            app_token: Slack app-level token (xapp-)
        """
        self.event_queue = event_queue
        self.bot_token = bot_token
        self.app_token = app_token
        self.handler: Optional[any] = None
        self._task: Optional[asyncio.Task] = None
        self.bot_user_id: Optional[str] = None
        
        # Import slack-bolt (lazy import to avoid dependency if not using Socket Mode)
        try:
            from slack_bolt.async_app import AsyncApp
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            self.AsyncApp = AsyncApp
            self.AsyncSocketModeHandler = AsyncSocketModeHandler
        except ImportError:
            logger.error("❌ slack-bolt not installed. Install with: pip install slack-bolt")
            raise
    
    async def start(self):
        """Start Socket Mode connection"""
        logger.info("🚀 Starting Slack Socket Mode...")
        logger.info("   ✅ No webhooks needed")
        logger.info("   ✅ No tunneling needed")
        logger.info("   ✅ No ngrok needed")
        logger.info("   📡 Connecting to Slack via WebSocket...")
        
        # Create Slack app
        app = self.AsyncApp(token=self.bot_token)
        
        # Get bot user ID for filtering mentions
        auth_response = await app.client.auth_test()
        self.bot_user_id = auth_response["user_id"]
        logger.info(f"   🤖 Bot user ID: {self.bot_user_id}")
        
        # Register event handlers
        self._register_handlers(app)
        
        # Create Socket Mode handler
        self.handler = self.AsyncSocketModeHandler(app, self.app_token)
        
        # Start in background task
        self._task = asyncio.create_task(self.handler.start_async())
        
        logger.info("✅ Socket Mode connected")
        logger.info("💡 Test by mentioning your bot in Slack: @cuga hello!")
    
    def _register_handlers(self, app):
        """Register Slack event handlers"""
        
        @app.event("app_mention")
        async def handle_app_mention(event, say):
            """Handle when bot is mentioned in a channel"""
            user = event["user"]
            text = event["text"]
            channel = event["channel"]
            ts = event["ts"]
            thread_ts = event.get("thread_ts")  # Check if this is already in a thread
            
            logger.info(f"📨 Received mention from {user} in {channel}")
            
            # Always respond in a thread:
            # - If already in a thread, use that thread_ts
            # - If top-level message, use the message ts to create a new thread
            response_thread_ts = thread_ts if thread_ts else ts
            
            # Create CUGA event
            cuga_event = Event(
                type=EventType.SLACK,
                source=EventSource.WEBHOOK,
                event_name="app_mention",
                payload={
                    "user": user,
                    "text": text,
                    "channel": channel,
                    "response_channel": channel,
                    "response_thread_ts": response_thread_ts,  # Always in thread
                },
                metadata={
                    "thread_id": f"slack_{channel}_{user}",
                    "user_id": user,
                }
            )
            
            # Queue event for processing
            await self.event_queue.enqueue(cuga_event)
            logger.info(f"✅ Event queued: app_mention from {user} (thread_ts={response_thread_ts})")
        
        @app.event("message")
        async def handle_message(event, say):
            """Handle direct messages to the bot"""
            # Ignore bot messages, threaded messages, and messages with bot mentions
            # (bot mentions are handled by app_mention event)
            text = event.get("text", "")
            
            if (event.get("subtype") == "bot_message" or
                event.get("thread_ts") or
                (self.bot_user_id and f"<@{self.bot_user_id}>" in text)):  # Skip if message contains bot mention
                return
            
            user = event.get("user")
            text = event.get("text", "")
            channel = event["channel"]
            ts = event["ts"]
            
            logger.info(f"💬 Received DM from {user}")
            
            # Create CUGA event
            cuga_event = Event(
                type=EventType.SLACK,
                source=EventSource.WEBHOOK,
                event_name="direct_message",
                payload={
                    "user": user,
                    "text": text,
                    "channel": channel,
                    "response_channel": channel,
                    "response_thread_ts": None,
                },
                metadata={
                    "thread_id": f"slack_{channel}_{user}",
                    "user_id": user,
                }
            )
            
            # Queue event for processing
            await self.event_queue.enqueue(cuga_event)
            logger.info(f"✅ Event queued: direct_message from {user}")
        
        @app.event("reaction_added")
        async def handle_reaction_added(event):
            """Handle emoji reaction added to a message"""
            reaction = event.get("reaction")
            user = event.get("user")
            item = event.get("item", {})
            channel = item.get("channel")

            logger.info(f"👍 Reaction :{reaction}: added by {user} in {channel}")

            cuga_event = Event(
                type=EventType.SLACK,
                source=EventSource.WEBHOOK,
                event_name="reaction_added",
                payload={
                    "reaction": reaction,
                    "user": user,
                    "item": item,
                    "item_user": event.get("item_user"),
                },
                metadata={
                    "session_target": "isolated",
                    "thread_id": f"slack_reaction_{channel}_{event.get('event_ts', '')}",
                },
            )

            await self.event_queue.enqueue(cuga_event)
            logger.info(f"✅ Event queued: reaction_added :{reaction}: from {user}")

        @app.event("reaction_removed")
        async def handle_reaction_removed(event):
            """Handle emoji reaction removed from a message"""
            reaction = event.get("reaction")
            user = event.get("user")
            item = event.get("item", {})
            channel = item.get("channel")

            logger.info(f"👎 Reaction :{reaction}: removed by {user} in {channel}")

            cuga_event = Event(
                type=EventType.SLACK,
                source=EventSource.WEBHOOK,
                event_name="reaction_removed",
                payload={
                    "reaction": reaction,
                    "user": user,
                    "item": item,
                    "item_user": event.get("item_user"),
                },
                metadata={
                    "session_target": "isolated",
                    "thread_id": f"slack_reaction_{channel}_{event.get('event_ts', '')}",
                },
            )

            await self.event_queue.enqueue(cuga_event)
            logger.info(f"✅ Event queued: reaction_removed :{reaction}: from {user}")

        @app.command("/cuga")
        async def handle_cuga_command(ack, command, respond):
            """Handle /cuga slash command"""
            await ack()  # Acknowledge immediately
            
            user = command["user_id"]
            text = command.get("text", "")
            channel = command["channel_id"]
            
            logger.info(f"⚡ Received /cuga command from {user}")
            
            # Create CUGA event
            cuga_event = Event(
                type=EventType.SLACK,
                source=EventSource.WEBHOOK,
                event_name="slash_command",
                payload={
                    "command": "/cuga",
                    "user": user,
                    "text": text,
                    "channel": channel,
                    "response_channel": channel,
                    "response_thread_ts": None,
                },
                metadata={
                    "thread_id": f"slack_{channel}_{user}",
                    "user_id": user,
                }
            )
            
            # Queue event for processing
            await self.event_queue.enqueue(cuga_event)
            logger.info(f"✅ Event queued: slash_command from {user}")
    
    async def stop(self):
        """Stop Socket Mode connection"""
        if self.handler:
            await self.handler.close_async()
            logger.info("✅ Socket Mode disconnected")
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

# Made with Bob
