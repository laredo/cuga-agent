"""Slack client wrapper"""

import asyncio
import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from slack_sdk.web.async_client import AsyncWebClient
    from slack_sdk.errors import SlackApiError
    SLACK_SDK_AVAILABLE = True
except ImportError:
    SLACK_SDK_AVAILABLE = False
    logger.warning("slack-sdk not installed. Install with: pip install slack-sdk")


class SlackClient:
    """Async Slack client wrapper"""
    
    def __init__(self, bot_token: str, signing_secret: str):
        if not SLACK_SDK_AVAILABLE:
            raise ImportError(
                "slack-sdk is required for Slack integration. "
                "Install with: pip install slack-sdk"
            )
        
        self.client = AsyncWebClient(token=bot_token)
        self.signing_secret = signing_secret
        
    def verify_signature(self, timestamp: str, body: str, signature: str) -> bool:
        """Verify Slack request signature
        
        Args:
            timestamp: X-Slack-Request-Timestamp header
            body: Raw request body as string
            signature: X-Slack-Signature header
            
        Returns:
            True if signature is valid, False otherwise
        """
        # Prevent replay attacks (timestamp must be within 5 minutes)
        if abs(time.time() - int(timestamp)) > 60 * 5:
            logger.warning("Slack request timestamp too old")
            return False
            
        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected_signature = "v0=" + hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send a message to a channel
        
        Args:
            channel: Channel ID
            text: Message text (fallback for notifications)
            thread_ts: Thread timestamp to reply in thread
            blocks: Slack blocks for rich formatting
            attachments: Message attachments
            
        Returns:
            Response data from Slack API
        """
        try:
            response = await self.client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts,
                blocks=blocks,
                attachments=attachments
            )
            return response.data
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error sending message: {e.response['error']}")
            else:
                logger.error(f"Error sending message: {e}")
            raise
    
    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Update an existing message
        
        Args:
            channel: Channel ID
            ts: Message timestamp
            text: New message text
            blocks: New blocks
            
        Returns:
            Response data from Slack API
        """
        try:
            response = await self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks
            )
            return response.data
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error updating message: {e.response['error']}")
            else:
                logger.error(f"Error updating message: {e}")
            raise
    
    async def add_reaction(self, channel: str, timestamp: str, emoji: str):
        """Add a reaction to a message
        
        Args:
            channel: Channel ID
            timestamp: Message timestamp
            emoji: Emoji name (without colons)
        """
        try:
            await self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error adding reaction: {e.response['error']}")
            else:
                logger.error(f"Error adding reaction: {e}")
            raise
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information
        
        Args:
            user_id: User ID
            
        Returns:
            User data from Slack API
        """
        try:
            response = await self.client.users_info(user=user_id)
            return response.data["user"]
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error getting user info: {e.response['error']}")
            else:
                logger.error(f"Error getting user info: {e}")
            raise
    
    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel information
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Channel data from Slack API
        """
        try:
            response = await self.client.conversations_info(channel=channel_id)
            return response.data["channel"]
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error getting channel info: {e.response['error']}")
            else:
                logger.error(f"Error getting channel info: {e}")
            raise
    
    async def upload_file(
        self,
        channels: List[str],
        file: bytes,
        filename: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file to Slack
        
        Args:
            channels: List of channel IDs
            file: File content as bytes
            filename: Filename
            title: File title
            initial_comment: Comment to post with file
            thread_ts: Thread timestamp to post in thread
            
        Returns:
            Response data from Slack API
        """
        try:
            response = await self.client.files_upload_v2(
                channels=channels,
                file=file,
                filename=filename,
                title=title,
                initial_comment=initial_comment,
                thread_ts=thread_ts
            )
            return response.data
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error uploading file: {e.response['error']}")
            else:
                logger.error(f"Error uploading file: {e}")
            raise
    
    async def open_modal(self, trigger_id: str, view: Dict[str, Any]) -> Dict[str, Any]:
        """Open a modal dialog
        
        Args:
            trigger_id: Trigger ID from interaction
            view: Modal view definition
            
        Returns:
            Response data from Slack API
        """
        try:
            response = await self.client.views_open(
                trigger_id=trigger_id,
                view=view
            )
            return response.data
        except Exception as e:
            if SLACK_SDK_AVAILABLE:
                from slack_sdk.errors import SlackApiError
                if isinstance(e, SlackApiError):
                    logger.error(f"Error opening modal: {e.response['error']}")
            else:
                logger.error(f"Error opening modal: {e}")
            raise

# Made with Bob
