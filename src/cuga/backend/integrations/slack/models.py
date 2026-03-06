"""Slack data models"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class SlackEventType(str, Enum):
    """Slack event types"""
    APP_MENTION = "app_mention"
    MESSAGE = "message"
    REACTION_ADDED = "reaction_added"
    REACTION_REMOVED = "reaction_removed"
    SLASH_COMMAND = "slash_command"
    INTERACTION = "interaction"


class SlackMessageType(str, Enum):
    """Slack message types"""
    CHANNEL = "channel"
    GROUP = "group"  # Private channel
    IM = "im"  # Direct message
    MPIM = "mpim"  # Multi-person DM


class SlackUser(BaseModel):
    """Slack user information"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: str
    username: Optional[str] = None
    real_name: Optional[str] = None
    email: Optional[str] = None
    is_bot: bool = False


class SlackChannel(BaseModel):
    """Slack channel information"""
    model_config = ConfigDict(use_enum_values=True)
    
    id: str
    name: Optional[str] = None
    is_private: bool = False
    is_im: bool = False


class SlackMessage(BaseModel):
    """Slack message"""
    model_config = ConfigDict(use_enum_values=True)
    
    text: str
    user: str
    ts: str  # Timestamp (message ID)
    channel: str
    channel_type: SlackMessageType
    thread_ts: Optional[str] = None  # Thread parent timestamp
    files: List[Dict[str, Any]] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    blocks: List[Dict[str, Any]] = Field(default_factory=list)


class SlackEvent(BaseModel):
    """Slack event payload"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: SlackEventType
    event_id: str
    event_time: datetime
    team_id: str
    user: Optional[SlackUser] = None
    channel: Optional[SlackChannel] = None
    message: Optional[SlackMessage] = None
    reaction: Optional[str] = None
    command: Optional[str] = None
    response_url: Optional[str] = None
    trigger_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SlackInteraction(BaseModel):
    """Slack interactive component"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: Literal["block_actions", "view_submission", "shortcut"]
    user: SlackUser
    channel: Optional[SlackChannel] = None
    message: Optional[SlackMessage] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    view: Optional[Dict[str, Any]] = None
    response_url: Optional[str] = None
    trigger_id: str

# Made with Bob
