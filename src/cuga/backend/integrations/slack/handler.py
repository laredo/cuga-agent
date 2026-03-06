"""Slack event handler - converts Slack events to CUGA events"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from cuga.backend.events.models import Event, EventType, EventSource
from cuga.backend.integrations.slack.client import SlackClient

logger = logging.getLogger(__name__)


class SlackEventHandler:
    """Handles Slack events and converts them to CUGA events"""
    
    def __init__(self, slack_client: SlackClient):
        self.slack_client = slack_client
    
    async def handle_event(self, payload: Dict[str, Any]) -> Optional[Event]:
        """Convert Slack event to CUGA event
        
        Args:
            payload: Slack event payload
            
        Returns:
            CUGA Event or None if event should be ignored
        """
        event_type = payload.get("event", {}).get("type")
        
        if event_type == "app_mention":
            return await self._handle_app_mention(payload)
        elif event_type == "message":
            return await self._handle_message(payload)
        elif event_type == "reaction_added":
            return await self._handle_reaction(payload, added=True)
        elif event_type == "reaction_removed":
            return await self._handle_reaction(payload, added=False)
        else:
            logger.warning(f"Unhandled Slack event type: {event_type}")
            return None
    
    async def _handle_app_mention(self, payload: Dict[str, Any]) -> Event:
        """Handle @mention of CUGA
        
        Args:
            payload: Slack event payload
            
        Returns:
            CUGA Event
        """
        event_data = payload["event"]
        
        # Get user and channel info
        user_info = await self.slack_client.get_user_info(event_data["user"])
        channel_info = await self.slack_client.get_channel_info(event_data["channel"])
        
        # Create CUGA event
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="app_mention",
            payload={
                "text": event_data["text"],
                "user": {
                    "id": user_info["id"],
                    "name": user_info.get("real_name", user_info.get("name")),
                    "email": user_info.get("profile", {}).get("email")
                },
                "channel": {
                    "id": channel_info["id"],
                    "name": channel_info.get("name"),
                    "is_private": channel_info.get("is_private", False)
                },
                "message_ts": event_data["ts"],
                "thread_ts": event_data.get("thread_ts"),
                "files": event_data.get("files", []),
                # Response routing info
                "response_channel": channel_info["id"],
                "response_thread_ts": event_data.get("thread_ts") or event_data["ts"]
            },
            metadata={
                "session_target": "main",  # Use main session for context
                "slack_team_id": payload["team_id"],
                "slack_event_id": payload["event_id"]
            }
        )
    
    async def _handle_message(self, payload: Dict[str, Any]) -> Optional[Event]:
        """Handle direct message to CUGA
        
        Args:
            payload: Slack event payload
            
        Returns:
            CUGA Event or None if message should be ignored
        """
        event_data = payload["event"]
        
        # Ignore bot messages and message changes
        if event_data.get("subtype") or event_data.get("bot_id"):
            return None
        
        # Only handle DMs (channel_type == "im")
        channel_type = event_data.get("channel_type")
        if channel_type != "im":
            return None
        
        user_info = await self.slack_client.get_user_info(event_data["user"])
        
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="direct_message",
            payload={
                "text": event_data["text"],
                "user": {
                    "id": user_info["id"],
                    "name": user_info.get("real_name", user_info.get("name")),
                    "email": user_info.get("profile", {}).get("email")
                },
                "channel": event_data["channel"],
                "message_ts": event_data["ts"],
                "thread_ts": event_data.get("thread_ts"),
                "files": event_data.get("files", []),
                # Response routing info
                "response_channel": event_data["channel"],
                "response_thread_ts": event_data.get("thread_ts") or event_data["ts"]
            },
            metadata={
                "session_target": "main",
                "slack_team_id": payload["team_id"],
                "slack_event_id": payload["event_id"]
            }
        )
    
    async def _handle_reaction(
        self, payload: Dict[str, Any], added: bool
    ) -> Event:
        """Handle reaction added/removed
        
        Args:
            payload: Slack event payload
            added: True if reaction was added, False if removed
            
        Returns:
            CUGA Event
        """
        event_data = payload["event"]
        
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="reaction_added" if added else "reaction_removed",
            payload={
                "reaction": event_data["reaction"],
                "user": event_data["user"],
                "item": event_data["item"],
                "item_user": event_data.get("item_user")
            },
            metadata={
                "session_target": "isolated",  # Reactions are independent
                "slack_team_id": payload["team_id"],
                "slack_event_id": payload["event_id"]
            }
        )
    
    async def handle_slash_command(self, payload: Dict[str, Any]) -> Event:
        """Handle slash command
        
        Args:
            payload: Slack slash command payload
            
        Returns:
            CUGA Event
        """
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="slash_command",
            payload={
                "command": payload["command"],
                "text": payload.get("text", ""),
                "user_id": payload["user_id"],
                "user_name": payload["user_name"],
                "channel_id": payload["channel_id"],
                "channel_name": payload.get("channel_name"),
                "response_url": payload["response_url"],
                "trigger_id": payload["trigger_id"],
                # Response routing info
                "response_channel": payload["channel_id"],
                "response_thread_ts": None  # Commands don't have threads
            },
            metadata={
                "session_target": "main",
                "slack_team_id": payload["team_id"]
            }
        )
    
    async def handle_interaction(self, payload: Dict[str, Any]) -> Event:
        """Handle interactive component (button, select, etc.)
        
        Args:
            payload: Slack interaction payload
            
        Returns:
            CUGA Event
        """
        # Extract action value for approval buttons
        action_value = None
        action_id = None
        if payload.get("actions"):
            action = payload["actions"][0]
            action_id = action.get("action_id")
            action_value = action.get("value")
        
        return Event(
            type=EventType.SLACK,
            source=EventSource.WEBHOOK,
            event_name="interaction",
            payload={
                "type": payload["type"],
                "user": payload["user"],
                "channel": payload.get("channel"),
                "message": payload.get("message"),
                "actions": payload.get("actions", []),
                "action_id": action_id,
                "action_value": action_value,
                "view": payload.get("view"),
                "response_url": payload.get("response_url"),
                "trigger_id": payload["trigger_id"],
                # Response routing info
                "response_channel": payload.get("channel", {}).get("id") if payload.get("channel") else None,
                "response_thread_ts": payload.get("message", {}).get("ts") if payload.get("message") else None
            },
            metadata={
                "session_target": "main",
                "slack_team_id": payload["team"]["id"]
            }
        )

# Made with Bob
