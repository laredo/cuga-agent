"""Slack-specific event processor"""

import os
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
    - Optional CUGA agent integration (controlled by CUGA_SLACK_ENABLE env var)
    """
    
    def __init__(
        self,
        notification_channel: SlackNotificationChannel,
        cuga_enabled: Optional[bool] = None
    ):
        """Initialize Slack event processor
        
        Args:
            notification_channel: Slack notification channel for sending responses
            cuga_enabled: Enable CUGA agent integration (default: from CUGA_SLACK_ENABLE env var)
        """
        self.notification = notification_channel
        self.cuga_enabled = (
            cuga_enabled
            if cuga_enabled is not None
            else os.getenv("CUGA_SLACK_ENABLE", "false").lower() == "true"
        )
        self.cuga_agent = None
        
        if self.cuga_enabled:
            try:
                from cuga.sdk import CugaAgent
                self.cuga_agent = CugaAgent()
                logger.info("✅ CUGA Slack integration enabled - AI responses active")
            except Exception as e:
                logger.error(f"Failed to initialize CUGA agent: {e}")
                self.cuga_enabled = False
        else:
            logger.info("ℹ️  CUGA Slack integration disabled (set CUGA_SLACK_ENABLE=true to enable)")
    
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
        user = event.payload.get("user", "")
        channel = event.payload.get("channel", "")
        response_channel = event.payload.get("response_channel")
        response_thread_ts = event.payload.get("response_thread_ts")
        
        logger.info(f"Slack message from {user}: {text[:50]}...")
        
        if not response_channel:
            logger.warning("No response channel in event payload")
            return
        
        # Send thinking indicator
        if response_thread_ts:
            await self.notification.send_thinking_indicator(
                channel=response_channel,
                message_ts=response_thread_ts
            )
        
        # Process with CUGA agent if enabled
        if self.cuga_enabled and self.cuga_agent:
            try:
                logger.info(f"Invoking CUGA agent for message: {text[:50]}...")
                
                # Use thread_id from session context for conversation continuity
                thread_id = session_context.thread_id or f"slack_{channel}_{user}"
                
                # Invoke CUGA agent
                result = await self.cuga_agent.invoke(
                    message=text,
                    thread_id=thread_id,
                    user_context=f"Slack user: {user}, Channel: {channel}"
                )
                
                response_text = result.answer
                logger.info(f"CUGA agent response: {response_text[:100]}...")
                
            except Exception as e:
                logger.error(f"Error invoking CUGA agent: {e}", exc_info=True)
                response_text = (
                    f"❌ Sorry, I encountered an error processing your request:\n"
                    f"```{str(e)}```\n\n"
                    f"_Please try again or contact support if the issue persists._"
                )
        else:
            # Fallback response when CUGA is disabled
            response_text = (
                f"Received your message: {text}\n\n"
                f"_Note: CUGA integration is currently disabled. "
                f"Set `CUGA_SLACK_ENABLE=true` in your environment to enable AI-powered responses._"
            )
        
        # Send response to Slack
        await self.notification.send_response(
            text=response_text,
            channel=response_channel,
            thread_ts=response_thread_ts
        )
        
        logger.info(f"Sent response to Slack channel {response_channel}")
    
    _APPROVE_REACTIONS = frozenset({"+1", "thumbsup", "white_check_mark"})
    _REJECT_REACTIONS = frozenset({"-1", "thumbsdown", "x"})

    async def _handle_reaction(self, event: Event, session_context: SessionContext):
        """Handle Slack reaction

        Only acts on reaction_added events. Maps known emojis to approval or
        rejection acknowledgments threaded on the original message.
        """
        if event.event_name != "reaction_added":
            return

        reaction = event.payload.get("reaction")
        item = event.payload.get("item") or {}
        channel = item.get("channel")
        thread_ts = item.get("ts")

        if not reaction or not channel:
            logger.warning(f"Reaction event missing required fields: reaction={reaction}, channel={channel}")
            return

        if reaction in self._APPROVE_REACTIONS:
            logger.info(f"Approval reaction '{reaction}' from {event.payload.get('user')} in {channel}")
            await self.notification.send_response(
                text="approved",
                channel=channel,
                thread_ts=thread_ts,
            )
        elif reaction in self._REJECT_REACTIONS:
            logger.info(f"Rejection reaction '{reaction}' from {event.payload.get('user')} in {channel}")
            await self.notification.send_response(
                text="rejected",
                channel=channel,
                thread_ts=thread_ts,
            )
        else:
            logger.info(f"Unrecognized reaction '{reaction}' — no action taken")
    
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
