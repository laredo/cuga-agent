"""Slack webhook routes for CUGA"""

import json
import os
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, HTTPException, Header
from loguru import logger

from cuga.backend.integrations.slack.client import SlackClient
from cuga.backend.integrations.slack.handler import SlackEventHandler
from cuga.backend.integrations.slack.notification_channel import SlackNotificationChannel
from cuga.backend.integrations.slack.processor import SlackEventProcessor
from cuga.backend.events.queue import EventQueue

router = APIRouter(prefix="/webhooks/slack", tags=["slack"])

# Global instances (will be initialized in lifespan)
slack_client: Optional[SlackClient] = None
slack_handler: Optional[SlackEventHandler] = None
slack_notification: Optional[SlackNotificationChannel] = None
slack_processor: Optional[SlackEventProcessor] = None
event_queue: Optional[EventQueue] = None


async def _build_multi_agent_runner():
    """Return a ConfigurationRunner if CUGA_SLACK_MULTI_AGENT_CONFIG is set, else None."""
    config_path = os.getenv("CUGA_SLACK_MULTI_AGENT_CONFIG")
    if not config_path:
        return None
    try:
        from cuga.backend.multi_agent.config import load_config
        from cuga.backend.multi_agent.agent_factory import AgentFactory
        from cuga.backend.multi_agent.runner import ConfigurationRunner

        cfg = load_config(config_path)
        factory = AgentFactory(cfg)
        await factory.__aenter__()
        runner = ConfigurationRunner(cfg, agents=factory.agents)
        logger.info(f"✅ Multi-agent runner loaded from {config_path}")
        return runner
    except Exception as e:
        logger.error(f"Failed to build multi-agent runner from {config_path}: {e}")
        return None


async def initialize_slack(queue: EventQueue) -> bool:
    """Initialize Slack integration components

    Args:
        queue: Event queue for enqueueing events

    Returns:
        True if initialization successful, False otherwise
    """
    global slack_client, slack_handler, slack_notification, slack_processor, event_queue
    
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    
    if not bot_token or not signing_secret:
        logger.warning(
            "Slack credentials not found. Set SLACK_BOT_TOKEN and "
            "SLACK_SIGNING_SECRET environment variables to enable Slack integration."
        )
        return False
    
    try:
        slack_client = SlackClient(
            bot_token=bot_token,
            signing_secret=signing_secret
        )
        slack_handler = SlackEventHandler(slack_client)
        slack_notification = SlackNotificationChannel(slack_client)

        runner = await _build_multi_agent_runner()
        slack_processor = SlackEventProcessor(slack_notification, multi_agent_runner=runner)
        event_queue = queue

        logger.info("✅ Slack integration initialized")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Slack integration: {e}")
        return False


@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack Events API callbacks
    
    This endpoint receives events from Slack such as:
    - app_mention: When @CUGA is mentioned in a channel
    - message: Direct messages to CUGA
    - reaction_added/removed: Emoji reactions on messages
    
    Args:
        request: FastAPI request object
        x_slack_request_timestamp: Slack request timestamp header
        x_slack_signature: Slack signature header for verification
        
    Returns:
        JSON response with challenge (for URL verification) or ok status
        
    Raises:
        HTTPException: If Slack integration not initialized or signature invalid
    """
    if not slack_client or not slack_handler or not event_queue:
        raise HTTPException(
            status_code=503,
            detail="Slack integration not initialized"
        )
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify Slack signature for security
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = json.loads(body_str)
    
    # Handle URL verification challenge (first-time setup)
    if payload.get("type") == "url_verification":
        logger.info("Slack URL verification challenge received")
        return {"challenge": payload["challenge"]}
    
    # Handle event callback
    if payload.get("type") == "event_callback":
        try:
            event = await slack_handler.handle_event(payload)
            if event:
                await event_queue.enqueue(event)
                logger.info(
                    f"Slack event enqueued: {event.event_name} "
                    f"from user {event.payload.get('user', {}).get('id', 'unknown')}"
                )
        except Exception as e:
            logger.error(f"Error handling Slack event: {e}")
            # Return 200 to prevent Slack retries for application errors
    
    return {"ok": True}


@router.post("/commands")
async def slack_commands(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack slash commands
    
    Supported commands:
    - /cuga [request]: Send request to CUGA
    - /cuga-approve [id]: Approve a pending action
    - /cuga-reject [id] [reason]: Reject a pending action
    - /cuga-status: Check CUGA status and pending approvals
    
    Args:
        request: FastAPI request object
        x_slack_request_timestamp: Slack request timestamp header
        x_slack_signature: Slack signature header for verification
        
    Returns:
        JSON response with ephemeral message
        
    Raises:
        HTTPException: If Slack integration not initialized or signature invalid
    """
    if not slack_client or not slack_handler or not event_queue:
        raise HTTPException(
            status_code=503,
            detail="Slack integration not initialized"
        )
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    payload = {k: v[0] for k, v in parse_qs(body_str).items()}
    
    try:
        event = await slack_handler.handle_slash_command(payload)
        await event_queue.enqueue(event)
        
        logger.info(
            f"Slash command enqueued: {payload.get('command', 'unknown')} "
            f"from user {payload.get('user_name', 'unknown')}"
        )
        
        # Immediate acknowledgment
        return {
            "response_type": "ephemeral",
            "text": "⏳ Processing your request..."
        }
    except Exception as e:
        logger.error(f"Error handling slash command: {e}")
        return {
            "response_type": "ephemeral",
            "text": f"❌ Error: {str(e)}"
        }


@router.post("/interactions")
async def slack_interactions(
    request: Request,
    x_slack_request_timestamp: str = Header(...),
    x_slack_signature: str = Header(...)
):
    """Handle Slack interactive components
    
    This endpoint receives interactions such as:
    - Button clicks (e.g., approval buttons)
    - Select menu choices
    - Modal submissions
    - Shortcuts
    
    Args:
        request: FastAPI request object
        x_slack_request_timestamp: Slack request timestamp header
        x_slack_signature: Slack signature header for verification
        
    Returns:
        JSON response with ok status
        
    Raises:
        HTTPException: If Slack integration not initialized or signature invalid
    """
    if not slack_client or not slack_handler or not event_queue:
        raise HTTPException(
            status_code=503,
            detail="Slack integration not initialized"
        )
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # Verify signature
    if not slack_client.verify_signature(
        x_slack_request_timestamp, body_str, x_slack_signature
    ):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse form data
    form_data = parse_qs(body_str)
    payload = json.loads(form_data["payload"][0])
    
    try:
        event = await slack_handler.handle_interaction(payload)
        await event_queue.enqueue(event)
        
        logger.info(
            f"Interaction enqueued: {payload.get('type', 'unknown')} "
            f"from user {payload.get('user', {}).get('id', 'unknown')}"
        )
        
        # Immediate acknowledgment
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling interaction: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/health")
async def slack_health():
    """Health check endpoint for Slack integration
    
    Returns:
        JSON response with integration status and component health
    """
    return {
        "status": "ok" if slack_client else "not_initialized",
        "integration": "slack",
        "components": {
            "client": slack_client is not None,
            "handler": slack_handler is not None,
            "notification": slack_notification is not None,
            "processor": slack_processor is not None,
            "queue": event_queue is not None
        },
        "queue_stats": event_queue.get_stats() if event_queue else None
    }


def get_slack_processor() -> Optional[SlackEventProcessor]:
    """Get the Slack event processor instance
    
    Returns:
        Slack event processor or None if not initialized
    """
    return slack_processor

# Made with Bob
