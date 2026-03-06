"""
CUGA Event System

Event-driven architecture for CUGA with support for:
- Webhooks (GitHub, Slack, custom)
- Cron scheduling
- Heartbeat monitoring
- Human-in-the-loop approvals
"""

from .models import Event, EventType, EventSource, EventPriority

__all__ = [
    "Event",
    "EventType",
    "EventSource",
    "EventPriority",
]

# Made with Bob
