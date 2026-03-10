"""Slack integration setup module

This module handles all Slack-specific initialization and keeps
Slack code isolated from the main CUGA codebase.

Supports two modes:
- Socket Mode (CUGA_SLACK_SOCKET_MODE=true): WebSocket connection, no public URL needed
- Webhook Mode (default): HTTP webhooks, requires public URL
"""

import asyncio
import os
from typing import Any, Optional
from loguru import logger

from cuga.backend.events.queue import EventQueue
from cuga.backend.events.processor import EventProcessor
from cuga.backend.events.session_management import SessionRouter, SessionManager
from cuga.backend.events.models import EventType
from cuga.backend.integrations.slack.routes import initialize_slack, get_slack_processor, router

# Global reference to Socket Mode handler for cleanup
_socket_mode_handler: Optional[Any] = None


async def setup_slack_integration(app: Any) -> None:
    """Setup Slack integration for CUGA
    
    This function:
    1. Detects mode (Socket Mode vs Webhook Mode)
    2. Creates the event queue, session manager, and session router
    3. Initializes Slack components (client, handler, processor)
    4. Registers the Slack event processor
    5. Starts the background event processing task
    6. For Webhook Mode: Adds webhook routes to FastAPI app
    7. For Socket Mode: Starts WebSocket connection to Slack
    
    Args:
        app: FastAPI application instance
    """
    global _socket_mode_handler
    
    try:
        # Check if Socket Mode is enabled
        socket_mode = os.getenv("CUGA_SLACK_SOCKET_MODE", "false").lower() in ("true", "1", "yes", "on")
        
        # Create event queue, session manager, and session router
        event_queue = EventQueue()
        session_manager = SessionManager()
        session_router = SessionRouter(manager=session_manager)
        
        # Initialize Slack components
        if not initialize_slack(event_queue):
            logger.warning("Slack integration enabled but initialization failed")
            return
        
        # Get the Slack processor and register it
        slack_processor = get_slack_processor()
        if not slack_processor:
            logger.error("Failed to get Slack processor")
            return
        
        # Create event processor with session router
        event_processor = EventProcessor(session_router)
        
        # Register Slack processor for Slack event type
        event_processor.register_processor(EventType.SLACK, slack_processor.process_event)
        
        # Background task to process events from the queue
        async def process_events():
            """Process events from the queue continuously"""
            logger.info("Slack event processor started")
            while True:
                try:
                    event = await event_queue.dequeue()
                    if event:
                        await event_processor.process_event(event)
                except Exception as e:
                    logger.error(f"Error processing Slack event: {e}")
                    # Continue processing even if one event fails
        
        # Start the background task
        task = asyncio.create_task(process_events())
        
        # Store task reference for cleanup
        if not hasattr(app.state, 'background_tasks'):
            app.state.background_tasks = []
        app.state.background_tasks.append(task)
        
        # Mode-specific setup
        if socket_mode:
            # Socket Mode: Start WebSocket connection
            app_token = os.getenv("SLACK_APP_TOKEN")
            bot_token = os.getenv("SLACK_BOT_TOKEN")
            
            if not app_token or not bot_token:
                logger.error("❌ SLACK_APP_TOKEN and SLACK_BOT_TOKEN required for Socket Mode")
                logger.error("   Get app token from: https://api.slack.com/apps → Your App → Basic Information → App-Level Tokens")
                logger.error("   Token should start with 'xapp-'")
                return
            
            try:
                from cuga.backend.integrations.slack.socket_mode import SocketModeHandler
                
                _socket_mode_handler = SocketModeHandler(
                    event_queue=event_queue,
                    bot_token=bot_token,  # Already checked for None above
                    app_token=app_token   # Already checked for None above
                )
                
                await _socket_mode_handler.start()
                
                # Store handler for cleanup
                app.state.slack_socket_handler = _socket_mode_handler
                
                logger.info("✅ Slack integration setup complete (Socket Mode)")
                logger.info("   - Event queue created")
                logger.info("   - Event processor registered")
                logger.info("   - Background task started")
                logger.info("   - Socket Mode connected")
                logger.info("   📡 Receiving events via WebSocket")
                
            except ImportError:
                logger.error("❌ slack-bolt not installed")
                logger.error("   Install with: pip install slack-bolt")
                return
        else:
            # Webhook Mode: Add HTTP routes
            app.include_router(router)
            
            logger.info("✅ Slack integration setup complete (Webhook Mode)")
            logger.info("   - Event queue created")
            logger.info("   - Event processor registered")
            logger.info("   - Background task started")
            logger.info("   - Webhook routes added at /webhooks/slack")
            logger.info("   🌐 Configure webhook URLs in Slack app settings")
        
    except Exception as e:
        logger.error(f"Failed to setup Slack integration: {e}")
        raise

# Made with Bob
