"""Slack-specific event processor"""

from typing import Optional
from loguru import logger

from cuga.backend.events.models import Event
from cuga.backend.events.session_management import SessionContext
from cuga.backend.integrations.slack.notification_channel import SlackNotificationChannel


class SlackEventProcessor:
    """Processes Slack events and sends responses back to Slack
    
    This processor handles all Slack-specific logic including:
    - Message handling (mentions, DMs, commands)
    - Interaction handling (buttons, modals)
    - Reaction handling
    - Error notifications
    """
    
    def __init__(self, notification_channel: SlackNotificationChannel):
        """Initialize Slack event processor
        
        Args:
            notification_channel: Slack notification channel for sending responses
        """
        self.notification = notification_channel
    
    async def process_event(self, event: Event, session_context: SessionContext):
        """Process a Slack event
        
        Args:
            event: Slack event to process
            session_context: Session context for processing
        """
        logger.info(f"Processing Slack event: {event.event_name}")
        
        try:
            # Handle different Slack event types
            if event.event_name == "interaction":
                await self._handle_interaction(event, session_context)
            elif event.event_name in ("app_mention", "direct_message", "slash_command"):
                await self._handle_message(event, session_context)
            elif event.event_name in ("reaction_added", "reaction_removed"):
                await self._handle_reaction(event, session_context)
            else:
                logger.warning(f"Unknown Slack event: {event.event_name}")
        
        except Exception as e:
            logger.error(f"Error processing Slack event {event.id}: {e}")
            await self._send_error(event, str(e))
    
    async def _handle_interaction(self, event: Event, session_context: SessionContext):
        """Handle Slack interaction (button click, modal submission, etc.)
        
        Args:
            event: Interaction event
            session_context: Session context
        """
        action_id = event.payload.get("action_id")
        action_value = event.payload.get("action_value")
        
        logger.info(f"Slack interaction: {action_id} = {action_value}")
        
        # Handle approval buttons
        if action_id == "approve_action":
            await self._handle_approval(event, action_value, approved=True)
        elif action_id == "reject_action":
            await self._handle_approval(event, action_value, approved=False)
        else:
            logger.warning(f"Unknown interaction action: {action_id}")
    
    async def _handle_approval(self, event: Event, approval_id: str, approved: bool):
        """Handle approval button click
        
        Args:
            event: Interaction event
            approval_id: Approval request ID
            approved: True if approved, False if rejected
        """
        logger.info(f"Approval: {approval_id} = {'approved' if approved else 'rejected'}")
        
        # TODO: Integrate with approval system
        # from cuga.backend.events.approval_system import ApprovalManager
        # approval_manager = ApprovalManager()
        # user_id = event.payload.get("user", {}).get("id")
        # if approved:
        #     approval_manager.approve_request(approval_id, approver=user_id)
        # else:
        #     approval_manager.reject_request(approval_id, approver=user_id)
        
        # Send confirmation
        response_channel = event.payload.get("response_channel")
        response_thread_ts = event.payload.get("response_thread_ts")
        
        if response_channel:
            status = "approved" if approved else "rejected"
            await self.notification.send_response(
                text=f"✅ Action {status}: {approval_id}",
                channel=response_channel,
                thread_ts=response_thread_ts
            )
    
    async def _handle_message(self, event: Event, session_context: SessionContext):
        """Handle Slack message (mention, DM, slash command)
        
        Args:
            event: Message event
            session_context: Session context
        """
        text = event.payload.get("text", "")
        user = event.payload.get("user", {})
        response_channel = event.payload.get("response_channel")
        response_thread_ts = event.payload.get("response_thread_ts")
        
        logger.info(f"Slack message from {user.get('name', 'unknown')}: {text[:50]}...")
        
        if not response_channel:
            logger.warning("No response channel in event payload")
            return
        
        # Send thinking indicator
        if response_thread_ts:
            await self.notification.send_thinking_indicator(
                channel=response_channel,
                message_ts=response_thread_ts
            )
        
        # TODO: Call CUGA agent here
        # from cuga.backend.cuga_graph.graph import DynamicAgentGraph
        # agent = DynamicAgentGraph()
        # response = await agent.process(text, session_context)
        
        # For now, send a placeholder response
        response_text = (
            f"Received your message: {text}\n\n"
            f"_Note: CUGA agent integration pending. "
            f"This is a test response from the Slack event processor._"
        )
        
        await self.notification.send_response(
            text=response_text,
            channel=response_channel,
            thread_ts=response_thread_ts
        )
        
        logger.info(f"Sent response to Slack channel {response_channel}")
    
    async def _handle_reaction(self, event: Event, session_context: SessionContext):
        """Handle Slack reaction
        
        Args:
            event: Reaction event
            session_context: Session context
        """
        reaction = event.payload.get("reaction")
        logger.info(f"Slack reaction: {reaction}")
        
        # TODO: Implement reaction handling
        # Could be used for:
        # - Feedback collection
        # - Bookmarking messages
        # - Quick actions (👍 = approve, 👎 = reject)
        # - etc.
    
    async def _send_error(self, event: Event, error_message: str):
        """Send error message to Slack
        
        Args:
            event: Event that caused the error
            error_message: Error message to send
        """
        response_channel = event.payload.get("response_channel")
        response_thread_ts = event.payload.get("response_thread_ts")
        
        if response_channel:
            try:
                await self.notification.send_response(
                    text=f"❌ Error processing your request: {error_message}",
                    channel=response_channel,
                    thread_ts=response_thread_ts
                )
                logger.info(f"Sent error notification to Slack channel {response_channel}")
            except Exception as e:
                logger.error(f"Failed to send error notification to Slack: {e}")

# Made with Bob
