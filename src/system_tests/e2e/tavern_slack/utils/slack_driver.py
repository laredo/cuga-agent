"""
Direct Slack Driver for Tavern Tests

Uses slack_sdk to directly interact with Slack API without MCP overhead.
Simpler, faster, and more reliable for testing.
"""

import time
from typing import Optional, Dict, List, Any
from loguru import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackDriver:
    """
    Driver for interacting with Slack via official SDK.
    Handles sending messages and waiting for bot responses.
    """

    def __init__(self, bot_token: str, target_bot_user_id: Optional[str] = None):
        """
        Initialize Slack driver.

        Args:
            bot_token: Slack bot token for test driver (xoxb-)
            target_bot_user_id: User ID of the bot to mention (e.g., CUGA bot)
                               If not provided, will use test driver's own ID
        """
        self.client = WebClient(token=bot_token)
        self.bot_user_id: Optional[str] = None  # Test driver's own user ID
        self.target_bot_user_id: Optional[str] = target_bot_user_id  # Bot to mention
        self.bot_mention: Optional[str] = None

    def initialize(self):
        """Initialize driver and get bot user IDs"""
        try:
            # Get test driver's own user ID
            response = self.client.auth_test()
            self.bot_user_id = response["user_id"]

            # Use target bot ID if provided, otherwise use own ID
            mention_user_id = self.target_bot_user_id or self.bot_user_id
            self.bot_mention = f"<@{mention_user_id}>"

            logger.info(
                f"✅ Slack driver initialized\n"
                f"   - Test driver ID: {self.bot_user_id}\n"
                f"   - Target bot ID: {mention_user_id}\n"
                f"   - Mention format: {self.bot_mention}"
            )
        except SlackApiError as e:
            logger.error(f"❌ Failed to initialize Slack driver: {e}")
            raise

    def format_mentions(self, text: str) -> str:
        """
        Convert @cuga mentions to proper Slack user ID format.

        Args:
            text: Message text with @cuga mentions

        Returns:
            Text with @cuga replaced by <@U0AKZPAEJRL>
        """
        if not self.bot_mention:
            return text

        # Replace @cuga with proper Slack mention format
        # This triggers app_mention events instead of just message events
        return text.replace("@cuga", self.bot_mention)

    def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message to Slack channel.

        Args:
            channel: Channel ID or name
            text: Message text
            thread_ts: Thread timestamp (optional)

        Returns:
            Message data including ts and channel
        """
        # Convert @cuga to proper Slack mention format
        formatted_text = self.format_mentions(text)

        logger.info(f"📤 Sending message to {channel}: {formatted_text[:50]}...")

        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=formatted_text,
                thread_ts=thread_ts
            )

            logger.info(f"✅ Message sent (ts: {response['ts']})")
            return {
                "ts": response["ts"],
                "channel": response["channel"],
                "text": formatted_text,
                "original_text": text
            }

        except SlackApiError as e:
            logger.error(f"❌ Failed to send message: {e}")
            raise

    def get_thread_messages(
        self,
        channel: str,
        thread_ts: str
    ) -> List[Dict[str, Any]]:
        """
        Get all messages in a thread.

        Args:
            channel: Channel ID
            thread_ts: Thread timestamp

        Returns:
            List of messages in thread
        """
        try:
            response = self.client.conversations_replies(
                channel=channel,
                ts=thread_ts
            )

            messages = response["messages"]
            return messages

        except SlackApiError as e:
            logger.error(f"❌ Failed to get thread messages: {e}")
            raise

    def get_channel_history(
        self,
        channel: str,
        limit: int = 10,
        oldest: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages from channel.

        Args:
            channel: Channel ID
            limit: Number of messages to retrieve
            oldest: Only messages after this timestamp

        Returns:
            List of messages
        """
        try:
            response = self.client.conversations_history(
                channel=channel,
                limit=limit,
                oldest=oldest
            )

            messages = response["messages"]
            return messages

        except SlackApiError as e:
            logger.error(f"❌ Failed to get channel history: {e}")
            raise

    def wait_for_response(
        self,
        channel: str,
        after_ts: str,
        thread_ts: Optional[str] = None,
        timeout: int = 30,
        poll_interval: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for bot response in channel or thread.

        Args:
            channel: Channel ID
            after_ts: Only return messages with timestamp > this value
            thread_ts: Thread timestamp (if waiting for threaded response)
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Bot's response message or None if timeout
        """
        # Determine which bot to look for responses from
        target_user_id = self.target_bot_user_id or self.bot_user_id

        logger.info(f"⏳ Waiting for response from bot {target_user_id} after {after_ts} (timeout: {timeout}s)...")

        start_time = time.time()
        last_check_ts = str(time.time())

        while time.time() - start_time < timeout:
            try:
                if thread_ts:
                    # Check thread for new messages
                    try:
                        messages = self.get_thread_messages(channel, thread_ts)
                        # Filter for target bot messages after the user message we just sent
                        for msg in messages:
                            if (msg.get("user") == target_user_id and
                                msg.get("ts") > after_ts):
                                logger.info(f"✅ Got bot response: {msg.get('text', '')[:50]}...")
                                return msg
                    except SlackApiError as thread_err:
                        # Thread might not exist yet if bot hasn't responded
                        if "thread_not_found" in str(thread_err):
                            # Fall back to channel history
                            # Bot might have created the thread with its first response
                            messages = self.get_channel_history(channel, limit=10, oldest=after_ts)
                            for msg in messages:
                                # Check if this is a bot message in the thread we're looking for
                                if (msg.get("user") == target_user_id and
                                    msg.get("ts") > after_ts and
                                    msg.get("thread_ts") == thread_ts):
                                    logger.info(f"✅ Got bot response from channel history: {msg.get('text', '')[:50]}...")
                                    return msg
                        else:
                            raise
                else:
                    # Check channel for new messages
                    messages = self.get_channel_history(channel, limit=5, oldest=last_check_ts)
                    # Filter for target bot messages after our sent message
                    for msg in messages:
                        if (msg.get("user") == target_user_id and
                            msg.get("ts") > after_ts):
                            logger.info(f"✅ Got bot response: {msg.get('text', '')[:50]}...")
                            return msg

                time.sleep(poll_interval)

            except SlackApiError as e:
                logger.warning(f"⚠️  Error while waiting for response: {e}")
                time.sleep(poll_interval)

        logger.warning(f"⏰ Timeout waiting for bot response after {timeout}s")
        return None

    def send_and_wait(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        timeout: int = 30
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Send message and wait for bot response.

        Args:
            channel: Channel ID
            text: Message text
            thread_ts: Thread timestamp (optional)
            timeout: Maximum time to wait for response

        Returns:
            Tuple of (sent_message, bot_response)
        """
        # Send message
        sent = self.send_message(channel, text, thread_ts)

        # Wait for response - always use sent["ts"] as the baseline.
        # CUGA always replies in a thread (using the user message ts as thread_ts),
        # so we look in the thread even for top-level messages.
        effective_thread_ts = thread_ts if thread_ts else sent["ts"]
        response = self.wait_for_response(
            channel=channel,
            after_ts=sent["ts"],
            thread_ts=effective_thread_ts,
            timeout=timeout
        )

        return sent, response


# Singleton instance for reuse across tests
_driver_instance: Optional[SlackDriver] = None


def get_driver() -> SlackDriver:
    """Get or create singleton driver instance"""
    global _driver_instance

    if _driver_instance is None:
        import os

        # Use TEST_DRIVER_* variables to keep test tokens separate from CUGA app tokens
        bot_token = os.getenv("TEST_DRIVER_SLACK_BOT_TOKEN")
        target_bot_user_id = os.getenv("CUGA_BOT_USER_ID")  # ID of bot to mention

        if not bot_token:
            raise ValueError(
                "TEST_DRIVER_SLACK_BOT_TOKEN must be set in environment"
            )

        if not target_bot_user_id:
            logger.warning(
                "⚠️  CUGA_BOT_USER_ID not set - will mention test driver itself. "
                "Set CUGA_BOT_USER_ID to mention the actual CUGA bot."
            )

        _driver_instance = SlackDriver(bot_token, target_bot_user_id)
        _driver_instance.initialize()

    return _driver_instance


def cleanup_driver():
    """Cleanup singleton driver instance"""
    global _driver_instance
    _driver_instance = None
    logger.info("✅ Slack driver cleaned up")

# Made with Bob
