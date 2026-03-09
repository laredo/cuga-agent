"""Slack integration for CUGA"""

from .models import (
    SlackEventType,
    SlackMessageType,
    SlackUser,
    SlackChannel,
    SlackMessage,
    SlackEvent,
    SlackInteraction,
)
from .client import SlackClient
from .handler import SlackEventHandler
from .notification_channel import SlackNotificationChannel
from .processor import SlackEventProcessor
from .routes import router, initialize_slack, get_slack_processor

__all__ = [
    "SlackEventType",
    "SlackMessageType",
    "SlackUser",
    "SlackChannel",
    "SlackMessage",
    "SlackEvent",
    "SlackInteraction",
    "SlackClient",
    "SlackEventHandler",
    "SlackNotificationChannel",
    "SlackEventProcessor",
    "router",
    "initialize_slack",
    "get_slack_processor",
]

# Made with Bob
