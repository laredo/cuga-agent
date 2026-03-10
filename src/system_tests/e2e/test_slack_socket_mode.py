#!/usr/bin/env python3
"""
Socket Mode test server for Slack integration.
No webhooks, tunneling, or ngrok needed!

Socket Mode uses WebSockets to connect directly from localhost to Slack.
Perfect for development and testing.
"""

import os
import asyncio
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv(".env.slack")

# Check for required environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

if not SLACK_BOT_TOKEN:
    logger.error("❌ SLACK_BOT_TOKEN not set in environment")
    logger.error("   Add it to .env.slack file")
    exit(1)

if not SLACK_APP_TOKEN:
    logger.error("❌ SLACK_APP_TOKEN not set in environment")
    logger.error("   Get it from: https://api.slack.com/apps → Your App → Basic Information → App-Level Tokens")
    logger.error("   Token should start with 'xapp-'")
    logger.error("   Add it to .env.slack file")
    exit(1)

if not SLACK_SIGNING_SECRET:
    logger.error("❌ SLACK_SIGNING_SECRET not set in environment")
    logger.error("   Add it to .env.slack file")
    exit(1)

# Import Slack libraries
try:
    from slack_bolt.async_app import AsyncApp
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
except ImportError:
    logger.error("❌ slack-bolt not installed")
    logger.error("   Install with: pip install slack-bolt")
    exit(1)

# Import CUGA components
from cuga.backend.events.queue import EventQueue
from cuga.backend.events.processor import EventProcessor
from cuga.backend.events.session_management import SessionRouter, SessionManager
from cuga.backend.events.models import Event, EventType, EventSource
from cuga.backend.integrations.slack.processor import SlackEventProcessor
from cuga.backend.integrations.slack.notification_channel import SlackNotificationChannel
from cuga.backend.integrations.slack.client import SlackClient

# Initialize Slack app
app = AsyncApp(token=SLACK_BOT_TOKEN)

# Global event system (will be initialized in main)
event_queue = None
session_manager = None
session_router = None
event_processor = None


@app.event("app_mention")
async def handle_app_mention(event, say, logger):
    """Handle when bot is mentioned in a channel"""
    user = event["user"]
    text = event["text"]
    channel = event["channel"]
    ts = event["ts"]
    
    logger.info(f"📨 Received mention from {user} in {channel}: {text}")
    
    # Create CUGA event
    cuga_event = Event(
        type=EventType.SLACK,
        source=EventSource.WEBHOOK,
        event_name="app_mention",
        payload={
            "user": user,
            "text": text,
            "channel": channel,
            "ts": ts,
        },
        metadata={
            "thread_id": channel,
            "user_id": user,
        }
    )
    
    # Queue event for processing
    await event_queue.enqueue(cuga_event)
    
    # Send immediate acknowledgment
    await say(f"👋 Hello <@{user}>! I received your message and I'm processing it...")
    
    # TODO: Integrate with CUGA agent for actual AI response
    # For now, just echo back
    response = f"You said: {text}\n\n_This is a test response. CUGA agent integration coming soon!_"
    await say(response, thread_ts=ts)


@app.event("message")
async def handle_message(event, say, logger):
    """Handle direct messages to the bot"""
    # Ignore bot messages, threaded messages, and messages that are also app_mentions
    # (app_mention handler will process those)
    if (event.get("subtype") == "bot_message" or
        event.get("thread_ts") or
        event.get("subtype") == "app_mention"):
        return
    
    user = event.get("user")
    text = event.get("text", "")
    channel = event["channel"]
    ts = event["ts"]
    
    logger.info(f"💬 Received DM from {user}: {text}")
    
    # Create CUGA event
    cuga_event = Event(
        type=EventType.SLACK,
        source=EventSource.WEBHOOK,
        event_name="message",
        payload={
            "user": user,
            "text": text,
            "channel": channel,
            "ts": ts,
        },
        metadata={
            "thread_id": channel,
            "user_id": user,
        }
    )
    
    # Queue event for processing
    await event_queue.enqueue(cuga_event)
    
    # Send response
    response = f"Hello! I received your message: {text}\n\n_CUGA agent integration coming soon!_"
    await say(response)


@app.command("/cuga")
async def handle_cuga_command(ack, command, respond, logger):
    """Handle /cuga slash command"""
    await ack()  # Acknowledge command immediately
    
    user = command["user_id"]
    text = command.get("text", "")
    channel = command["channel_id"]
    
    logger.info(f"⚡ Received /cuga command from {user}: {text}")
    
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
        },
        metadata={
            "thread_id": channel,
            "user_id": user,
        }
    )
    
    # Queue event for processing
    await event_queue.enqueue(cuga_event)
    
    # Send response
    response = f"Processing your request: {text}\n\n_CUGA agent integration coming soon!_"
    await respond(response)


async def main():
    """Main function to start the Socket Mode handler"""
    global event_queue, session_manager, session_router, event_processor
    
    logger.info("🚀 Starting CUGA Slack bot in Socket Mode...")
    logger.info("   ✅ No webhooks needed")
    logger.info("   ✅ No tunneling needed")
    logger.info("   ✅ No ngrok needed")
    logger.info("   📡 Connecting directly to Slack via WebSocket...")
    logger.info("")
    logger.info(f"   Bot Token: {SLACK_BOT_TOKEN[:20]}...")
    logger.info(f"   App Token: {SLACK_APP_TOKEN[:20]}...")
    logger.info("")
    
    # Initialize event system
    event_queue = EventQueue(max_size=100)
    session_manager = SessionManager()
    session_router = SessionRouter(manager=session_manager)
    event_processor = EventProcessor(session_router)
    
    # Initialize Slack integration
    slack_client = SlackClient(bot_token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
    slack_notification = SlackNotificationChannel(slack_client=slack_client)
    slack_processor = SlackEventProcessor(notification_channel=slack_notification)
    
    # Register Slack processor for Slack events
    event_processor.register_processor(EventType.SLACK, slack_processor.process_event)
    logger.info("✅ Slack processor registered")
    
    # Start event queue processor
    event_queue.start_processor(event_processor.process_event)
    logger.info("✅ Event queue started")
    
    logger.info("")
    logger.info("💡 Test by mentioning your bot in Slack:")
    logger.info("   @cuga hello!")
    logger.info("")
    
    # Create Socket Mode handler
    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    
    # Start the handler
    await handler.start_async()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down gracefully...")
        # Stop event queue
        asyncio.run(event_queue.stop())
        logger.info("✅ Shutdown complete")

# Made with Bob
