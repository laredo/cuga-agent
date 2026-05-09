"""
Standalone runner for the Chief of Staff Research multi-agent example.

Loads topology.toml, builds agents, and connects to Slack via Socket Mode.
Also starts a local dashboard on http://localhost:7860 with live agent logs
and links to Langfuse traces.

Usage:
    cd docs/examples/chief_of_staff_research
    cp .env.example .env && vim .env
    python run.py

Two Slack workflows:
    Research:  "@bot research quantum computing"
    Summary:   "@bot summarize what we know about quantum computing"

Required env vars (copy .env.example to .env):
    OPENAI_API_KEY / MODEL_NAME / OPENAI_BASE_URL
    SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET
    CUGA_SLACK_SOCKET_MODE=true

Optional:
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
    DASHBOARD_PORT  (default 7860)
"""

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent / ".env")

TOPOLOGY = Path(__file__).parent / "topology.toml"


async def main():
    from observability import setup_langfuse, setup_swarm_logging, ToolCallLoggingCallback
    from dashboard import start as start_dashboard

    from cuga.backend.multi_agent.config import load_config
    from cuga.backend.multi_agent.swarm_factory import SwarmAgentFactory
    from cuga.backend.multi_agent.runner import ConfigurationRunner
    from cuga.backend.integrations.slack.client import SlackClient
    from cuga.backend.integrations.slack.notification_channel import SlackNotificationChannel
    from cuga.backend.integrations.slack.processor import SlackEventProcessor
    from cuga.backend.integrations.slack.socket_mode import SocketModeHandler
    from cuga.backend.events.queue import EventQueue
    from cuga.backend.events.processor import EventProcessor
    from cuga.backend.events.session_management import SessionRouter, SessionManager
    from cuga.backend.events.models import EventType

    # -- Observability -------------------------------------------------------
    setup_swarm_logging()
    callbacks = [ToolCallLoggingCallback()]
    langfuse_handler = setup_langfuse()
    if langfuse_handler:
        callbacks.append(langfuse_handler)

    # -- Topology ------------------------------------------------------------
    cfg = load_config(TOPOLOGY)
    logger.info(f"Loaded topology '{cfg.name}' ({cfg.pattern}, {len(cfg.agents)} agents)")

    async with SwarmAgentFactory(cfg) as factory:
        runner = ConfigurationRunner(
            cfg,
            agents=factory.agents,
            callbacks=callbacks,
            agent_queues=factory.agent_queues,
        )
        logger.info("Multi-agent runner ready")
        for a in cfg.agents:
            logger.info(f"  • {a.id:<22} role={a.role}  domain={a.domain or '-'}")

        # -- Dashboard -------------------------------------------------------
        port = int(os.getenv("DASHBOARD_PORT", "7860"))
        asyncio.create_task(start_dashboard(port=port))

        # -- Slack -----------------------------------------------------------
        bot_token      = os.environ["SLACK_BOT_TOKEN"]
        signing_secret = os.environ["SLACK_SIGNING_SECRET"]
        app_token      = os.environ["SLACK_APP_TOKEN"]

        slack_client = SlackClient(bot_token=bot_token, signing_secret=signing_secret)
        notification = SlackNotificationChannel(slack_client)
        processor    = SlackEventProcessor(notification, multi_agent_runner=runner)

        event_queue    = EventQueue()
        session_router = SessionRouter(manager=SessionManager())
        event_proc     = EventProcessor(session_router)
        event_proc.register_processor(EventType.SLACK, processor.process_event)

        async def drain():
            while True:
                event = await event_queue.dequeue()
                if event:
                    await event_proc.process_event(event)

        asyncio.create_task(drain())

        socket_handler = SocketModeHandler(
            event_queue=event_queue,
            bot_token=bot_token,
            app_token=app_token,
        )
        logger.info("Starting Slack Socket Mode")
        logger.info("  Try: '@bot research <topic>'  or  '@bot summarize <topic>'")
        logger.info(f"  Dashboard: http://localhost:{port}")
        await socket_handler.start()
        await asyncio.get_event_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
