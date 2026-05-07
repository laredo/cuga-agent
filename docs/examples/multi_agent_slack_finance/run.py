"""
Standalone runner for the Slack ↔ Finance Quote multi-agent example.

Loads topology.toml, builds agents (with cuga-finance MCP), and hooks them
into the Slack processor so every Slack message is handled by the two-agent
pipeline instead of a single CugaAgent.

Usage:
    cd docs/examples/multi_agent_slack_finance
    python run.py

Required env vars (copy .env.example to .env and fill in):
    OPENAI_API_KEY          (or whichever LLM provider you configure)
    SLACK_BOT_TOKEN
    SLACK_APP_TOKEN
    SLACK_SIGNING_SECRET
    CUGA_SLACK_SOCKET_MODE=true
"""

import asyncio
import os
import sys
from pathlib import Path

# Allow importing cuga from the repo root without installing
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent / ".env")

TOPOLOGY = Path(__file__).parent / "topology.toml"


async def main():
    from cuga.backend.multi_agent.config import load_config
    from cuga.backend.multi_agent.agent_factory import AgentFactory
    from cuga.backend.multi_agent.runner import ConfigurationRunner
    from cuga.backend.integrations.slack.client import SlackClient
    from cuga.backend.integrations.slack.notification_channel import SlackNotificationChannel
    from cuga.backend.integrations.slack.processor import SlackEventProcessor
    from cuga.backend.integrations.slack.socket_mode import SocketModeHandler
    from cuga.backend.events.queue import EventQueue
    from cuga.backend.events.processor import EventProcessor
    from cuga.backend.events.session_management import SessionRouter, SessionManager
    from cuga.backend.events.models import EventType

    # ── Load topology and build agents ───────────────────────────────────────
    cfg = load_config(TOPOLOGY)
    logger.info(f"Loaded topology '{cfg.name}' ({cfg.pattern}, {len(cfg.agents)} agents)")

    async with AgentFactory(cfg) as factory:
        runner = ConfigurationRunner(cfg, agents=factory.agents)
        logger.info("Multi-agent runner ready")

        # ── Wire into Slack ───────────────────────────────────────────────────
        bot_token      = os.environ["SLACK_BOT_TOKEN"]
        signing_secret = os.environ["SLACK_SIGNING_SECRET"]
        app_token      = os.environ["SLACK_APP_TOKEN"]

        slack_client   = SlackClient(bot_token=bot_token, signing_secret=signing_secret)
        notification   = SlackNotificationChannel(slack_client)
        processor      = SlackEventProcessor(notification, multi_agent_runner=runner)

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
        logger.info("Starting Slack Socket Mode — send a stock or crypto query to your bot")
        await socket_handler.start()
        # Keep running until interrupted
        await asyncio.get_event_loop().create_future()


if __name__ == "__main__":
    asyncio.run(main())
