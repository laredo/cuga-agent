#!/usr/bin/env python3
"""
Test script for Slack webhook integration.

This script creates a minimal FastAPI server with the Slack webhook endpoints
so you can test the integration without modifying the main CUGA server.

Usage:
    1. Set up environment variables in .env.slack:
       SLACK_BOT_TOKEN=xoxb-your-bot-token
       SLACK_SIGNING_SECRET=your-signing-secret
       
    2. Run this script:
       python test_slack_integration.py
       
    3. In another terminal, start ngrok:
       ngrok http 8001
       
    4. Update your Slack app's webhook URLs with the ngrok URL:
       - Events: https://your-ngrok-url.ngrok.io/webhooks/slack/events
       - Commands: https://your-ngrok-url.ngrok.io/webhooks/slack/commands
       - Interactions: https://your-ngrok-url.ngrok.io/webhooks/slack/interactions
       
    5. Test by mentioning your bot in Slack or using a slash command
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.slack")

# Import our Slack integration components
from cuga.backend.events.queue import EventQueue
from cuga.backend.events.processor import EventProcessor
from cuga.backend.events.session_management import SessionRouter, SessionManager
from cuga.backend.events.models import EventType
from cuga.backend.integrations.slack import (
    router as slack_router,
    initialize_slack,
    get_slack_processor,
)


class TestAppState:
    """Minimal app state for testing."""
    
    def __init__(self):
        self.event_queue: Optional[EventQueue] = None
        self.event_processor: Optional[EventProcessor] = None
        self.session_manager: Optional[SessionManager] = None
        self.session_router: Optional[SessionRouter] = None


# Global app state
test_app_state = TestAppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Slack webhook test server...")
    
    # Initialize event system
    test_app_state.event_queue = EventQueue(max_size=100)
    test_app_state.session_manager = SessionManager()
    test_app_state.session_router = SessionRouter(manager=test_app_state.session_manager)
    test_app_state.event_processor = EventProcessor(test_app_state.session_router)
    
    # Start event queue processor
    test_app_state.event_queue.start_processor(test_app_state.event_processor.process_event)
    logger.info("✅ Event queue started")
    
    # Initialize Slack integration
    if initialize_slack(test_app_state.event_queue):
        slack_processor = get_slack_processor()
        if slack_processor:
            # Register Slack processor with the event processor
            test_app_state.event_processor.register_processor(
                EventType.SLACK,
                slack_processor.process_event
            )
            logger.success("✅ Slack integration initialized")
            logger.info(f"   Bot Token: {os.getenv('SLACK_BOT_TOKEN', 'NOT SET')[:20]}...")
            logger.info(f"   Signing Secret: {os.getenv('SLACK_SIGNING_SECRET', 'NOT SET')[:20]}...")
        else:
            logger.error("❌ Failed to get Slack processor")
    else:
        logger.error("❌ Failed to initialize Slack integration")
        logger.error("   Make sure SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET are set in .env.slack")
    
    logger.info("🌐 Server ready at http://localhost:8001")
    logger.info("📝 Endpoints:")
    logger.info("   - POST /webhooks/slack/events")
    logger.info("   - POST /webhooks/slack/commands")
    logger.info("   - POST /webhooks/slack/interactions")
    logger.info("   - GET  /webhooks/slack/health")
    logger.info("")
    logger.info("💡 Next steps:")
    logger.info("   1. Start ngrok: ngrok http 8001")
    logger.info("   2. Update Slack app webhook URLs with ngrok URL")
    logger.info("   3. Test by mentioning your bot in Slack")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down...")
    if test_app_state.event_queue:
        await test_app_state.event_queue.stop()
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Slack Webhook Test Server",
    description="Test server for CUGA Slack integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Slack router
app.include_router(slack_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Slack Webhook Test Server",
        "status": "running",
        "endpoints": {
            "events": "/webhooks/slack/events",
            "commands": "/webhooks/slack/commands",
            "interactions": "/webhooks/slack/interactions",
            "health": "/webhooks/slack/health",
        },
        "event_queue_stats": test_app_state.event_queue.get_stats() if test_app_state.event_queue else None,
    }


@app.get("/stats")
async def stats():
    """Get event queue statistics."""
    if not test_app_state.event_queue:
        return {"error": "Event queue not initialized"}
    
    stats = {
        "event_queue": test_app_state.event_queue.get_stats(),
    }
    
    if test_app_state.session_manager:
        stats["session_manager"] = test_app_state.session_manager.get_statistics()
    
    return stats


if __name__ == "__main__":
    import uvicorn
    
    # Check environment variables
    if not os.getenv("SLACK_BOT_TOKEN"):
        logger.error("❌ SLACK_BOT_TOKEN not set in environment")
        logger.error("   Create .env.slack file with your Slack credentials")
        exit(1)
    
    if not os.getenv("SLACK_SIGNING_SECRET"):
        logger.error("❌ SLACK_SIGNING_SECRET not set in environment")
        logger.error("   Create .env.slack file with your Slack credentials")
        exit(1)
    
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )

# Made with Bob
