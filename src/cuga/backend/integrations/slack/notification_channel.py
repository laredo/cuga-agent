"""Slack notification channel for CUGA responses and approvals"""

from typing import Dict, Any, List, Optional
import logging

from cuga.backend.integrations.slack.client import SlackClient

logger = logging.getLogger(__name__)


class SlackNotificationChannel:
    """Slack notification channel for approvals and responses"""
    
    def __init__(self, slack_client: SlackClient):
        self.slack_client = slack_client
    
    async def send_approval_request(
        self,
        approval_request: Dict[str, Any],
        channel: str,
        thread_ts: Optional[str] = None
    ):
        """Send approval request to Slack with interactive buttons
        
        Args:
            approval_request: Approval request data with 'id' and 'action'
            channel: Slack channel ID
            thread_ts: Thread timestamp to reply in thread
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Approval Required*\n\n{approval_request['action']}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Request ID: `{approval_request['id']}`"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "action_id": "approve_action",
                        "value": approval_request['id']
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "style": "danger",
                        "action_id": "reject_action",
                        "value": approval_request['id']
                    }
                ]
            }
        ]
        
        # Add context if available
        if approval_request.get('context'):
            blocks.insert(1, {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Context:*\n```{approval_request['context']}```"
                }
            })
        
        await self.slack_client.send_message(
            channel=channel,
            text=f"Approval required: {approval_request['action']}",
            thread_ts=thread_ts,
            blocks=blocks
        )
        
        logger.info(f"Sent approval request {approval_request['id']} to Slack channel {channel}")
    
    async def send_response(
        self,
        text: str,
        channel: str,
        thread_ts: Optional[str] = None
    ):
        """Send agent response to Slack
        
        Args:
            text: Response text
            channel: Slack channel ID
            thread_ts: Thread timestamp to reply in thread
        """
        # Format response with blocks for better UX
        blocks = self._format_response_blocks(text)
        
        await self.slack_client.send_message(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks
        )
        
        logger.info(f"Sent response to Slack channel {channel}")
    
    async def send_thinking_indicator(
        self,
        channel: str,
        message_ts: str
    ):
        """Add thinking reaction to indicate processing
        
        Args:
            channel: Slack channel ID
            message_ts: Message timestamp
        """
        try:
            await self.slack_client.add_reaction(
                channel=channel,
                timestamp=message_ts,
                emoji="thinking_face"
            )
        except Exception as e:
            logger.warning(f"Failed to add thinking reaction: {e}")
    
    async def send_completion_indicator(
        self,
        channel: str,
        message_ts: str
    ):
        """Add completion reaction
        
        Args:
            channel: Slack channel ID
            message_ts: Message timestamp
        """
        try:
            await self.slack_client.add_reaction(
                channel=channel,
                timestamp=message_ts,
                emoji="white_check_mark"
            )
        except Exception as e:
            logger.warning(f"Failed to add completion reaction: {e}")
    
    async def send_error_indicator(
        self,
        channel: str,
        message_ts: str
    ):
        """Add error reaction
        
        Args:
            channel: Slack channel ID
            message_ts: Message timestamp
        """
        try:
            await self.slack_client.add_reaction(
                channel=channel,
                timestamp=message_ts,
                emoji="x"
            )
        except Exception as e:
            logger.warning(f"Failed to add error reaction: {e}")
    
    def _format_response_blocks(self, text: str) -> List[Dict[str, Any]]:
        """Format text into Slack blocks
        
        Args:
            text: Response text
            
        Returns:
            List of Slack blocks
        """
        max_length = 3000
        blocks = []
        
        if len(text) <= max_length:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            })
        else:
            # Split into chunks
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            for chunk in chunks:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": chunk}
                })
        
        return blocks
    
    async def update_approval_message(
        self,
        channel: str,
        message_ts: str,
        approval_request: Dict[str, Any],
        status: str,
        approver: Optional[str] = None
    ):
        """Update approval message with decision
        
        Args:
            channel: Slack channel ID
            message_ts: Message timestamp
            approval_request: Original approval request
            status: "approved" or "rejected"
            approver: User who made the decision
        """
        status_emoji = "✅" if status == "approved" else "❌"
        status_text = "Approved" if status == "approved" else "Rejected"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"~*Approval Required*~\n\n{approval_request['action']}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *{status_text}*" + (f" by <@{approver}>" if approver else "")
                    }
                ]
            }
        ]
        
        await self.slack_client.update_message(
            channel=channel,
            ts=message_ts,
            text=f"{status_text}: {approval_request['action']}",
            blocks=blocks
        )
        
        logger.info(f"Updated approval message {message_ts} with status {status}")

# Made with Bob
