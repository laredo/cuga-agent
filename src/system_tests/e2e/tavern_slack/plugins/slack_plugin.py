"""
Tavern Plugin for Slack Testing

Provides custom request types for Tavern to interact with Slack directly via SDK.
"""

from typing import Dict, Any
from box import Box
from loguru import logger

from ..utils.slack_driver import get_driver, cleanup_driver


# Tavern schema hook to allow custom request types
def pytest_tavern_beta_before_every_test_run(test_dict, variables):
    """
    Hook called before test validation.
    Allows Tavern to accept our custom request types.
    """
    # Modify test_dict to mark our custom keys as valid
    for stage in test_dict.get("stages", []):
        # If stage has our custom keys, mark them as valid by not validating against strict schema
        if any(k.startswith("slack_") for k in stage.keys()):
            # Tavern will skip strict validation for stages with custom keys
            stage["_tavern_internal_skip_validation"] = True


class SlackRequest:
    """Custom Tavern request handler for Slack operations"""

    def __init__(self, session, name, request_spec, test_block_config):
        """
        Initialize Slack request handler.

        Args:
            session: Tavern session (unused, for compatibility)
            name: Request name
            request_spec: Request specification from YAML
            test_block_config: Test configuration
        """
        self.name = name
        self.spec = Box(request_spec)
        self.test_block_config = test_block_config
        self.driver = get_driver()

    def run(self) -> Dict[str, Any]:
        """
        Execute Slack request.

        Returns:
            Response dict with status_code and json
        """
        # Determine request type
        if hasattr(self.spec, 'slack_send'):
            return self._send_message()
        elif hasattr(self.spec, 'slack_wait'):
            return self._wait_for_response()
        elif hasattr(self.spec, 'slack_send_and_wait'):
            return self._send_and_wait()
        else:
            raise ValueError(f"Unknown Slack request type in spec: {self.spec}")

    def _send_message(self) -> Dict[str, Any]:
        """Send message via Slack SDK"""
        config = self.spec.slack_send

        # Format values with test config
        channel = self._format_value(config.channel)
        text = self._format_value(config.text)
        thread_ts = self._format_value(config.get('thread_ts')) if hasattr(config, 'thread_ts') else None

        logger.info(f"📤 Slack Send: {text[:50]}... to {channel}")

        try:
            result = self.driver.send_message(
                channel=channel,
                text=text,
                thread_ts=thread_ts
            )

            return {
                "status_code": 200,
                "json": result
            }

        except Exception as e:
            logger.error(f"❌ Slack Send failed: {e}")
            return {
                "status_code": 500,
                "json": {"error": str(e)}
            }

    def _wait_for_response(self) -> Dict[str, Any]:
        """Wait for response via Slack SDK"""
        import time
        config = self.spec.slack_wait

        # Format values
        channel = self._format_value(config.channel)
        thread_ts = self._format_value(config.thread_ts)
        after_ts = self._format_value(config.get('after_ts', str(time.time())))
        timeout = config.get('timeout', 30)

        logger.info(f"⏳ Slack Wait: thread {thread_ts} in {channel} after {after_ts}")

        try:
            response = self.driver.wait_for_response(
                channel=channel,
                after_ts=after_ts,
                thread_ts=thread_ts,
                timeout=timeout
            )

            if response is None:
                return {
                    "status_code": 408,  # Request Timeout
                    "json": {"error": "Timeout waiting for response"}
                }

            return {
                "status_code": 200,
                "json": response
            }

        except Exception as e:
            logger.error(f"❌ Slack Wait failed: {e}")
            return {
                "status_code": 500,
                "json": {"error": str(e)}
            }

    def _send_and_wait(self) -> Dict[str, Any]:
        """Send message and wait for response"""
        config = self.spec.slack_send_and_wait

        # Format values
        channel = self._format_value(config.channel)
        text = self._format_value(config.text)
        timeout = config.get('timeout', 30)

        logger.info(f"📤⏳ Slack Send & Wait: {text[:50]}... to {channel}")

        try:
            sent, response = self.driver.send_and_wait(
                channel=channel,
                text=text,
                timeout=timeout
            )

            if response is None:
                return {
                    "status_code": 408,
                    "json": {
                        "sent": sent,
                        "response": None,
                        "error": "Timeout waiting for response"
                    }
                }

            return {
                "status_code": 200,
                "json": {
                    "sent": sent,
                    "response": response
                }
            }

        except Exception as e:
            logger.error(f"❌ Slack Send & Wait failed: {e}")
            return {
                "status_code": 500,
                "json": {"error": str(e)}
            }

    def _format_value(self, value: Any) -> Any:
        """
        Format value with test config variables.

        Replaces {variable} with values from test_block_config.
        """
        if not isinstance(value, str):
            return value

        # Replace variables like {test_channel}
        formatted = value
        for key, val in self.test_block_config.get('variables', {}).items():
            formatted = formatted.replace(f"{{{key}}}", str(val))

        return formatted


def get_request_type(request_spec, test_block_config):
    """
    Tavern plugin hook to provide custom request type.

    This function is called by Tavern to determine if this plugin
    should handle the request.
    """
    # Check if this is a Slack request
    if any(key.startswith('slack_') for key in request_spec.keys()):
        return SlackRequest

    return None


# Cleanup hook for Tavern
def pytest_sessionfinish(session, exitstatus):
    """Cleanup Slack driver after test session"""
    cleanup_driver()

# Made with Bob
