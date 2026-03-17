"""
Pytest configuration for Tavern Slack tests.

Provides fixtures and configuration for Slack integration tests.
"""

import os
import pytest
import asyncio
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logger.info(f"✅ Loaded environment from {env_file}")
else:
    logger.warning(f"⚠️  No .env file found at {env_file}")

# Import plugin to register it (for custom Tavern extensions if needed)
from .plugins import slack_plugin


# Configure pytest for async tests
def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "slack: mark test as Slack integration test"
    )


@pytest.fixture(scope="session")
def test_channel():
    """
    Primary test channel ID for running tests.

    Set via SLACK_TEST_CHANNEL environment variable.
    This is the default channel used when tests don't specify one.
    """
    channel = os.getenv("SLACK_TEST_CHANNEL")
    if not channel:
        pytest.skip("SLACK_TEST_CHANNEL not set")
    return channel


@pytest.fixture(scope="session")
def test_channels():
    """
    List of test channel IDs for running tests.

    Set via SLACK_TEST_CHANNELS environment variable (comma-separated).
    Returns list of channel IDs that can be used for different test scenarios.
    """
    channels_str = os.getenv("SLACK_TEST_CHANNELS", "")
    if not channels_str:
        # Fall back to single channel if SLACK_TEST_CHANNELS not set
        channel = os.getenv("SLACK_TEST_CHANNEL")
        if channel:
            return [channel]
        pytest.skip("Neither SLACK_TEST_CHANNELS nor SLACK_TEST_CHANNEL set")

    # Parse comma-separated list and strip whitespace
    channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]
    if not channels:
        pytest.skip("SLACK_TEST_CHANNELS is empty")

    return channels


@pytest.fixture(scope="session")
def bot_mention():
    """
    Bot mention format for tests.

    Returns @cuga or custom mention from SLACK_BOT_MENTION env var.
    """
    return os.getenv("SLACK_BOT_MENTION", "@cuga")


@pytest.fixture(scope="session")
def tavern_global_cfg(test_channel, test_channels, bot_mention):
    """
    Global configuration for all Tavern tests.

    Provides variables that can be used in YAML specs.
    """
    return {
        "variables": {
            "test_channel": test_channel,  # Primary channel (backward compatibility)
            "test_channels": test_channels,  # List of all test channels
            "bot_mention": bot_mention,
            "default_timeout": 30,
        }
    }


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Setup logging for tests"""
    logger.info("=" * 60)
    logger.info("Starting Tavern Slack Test Session")
    logger.info("=" * 60)

    yield

    logger.info("=" * 60)
    logger.info("Tavern Slack Test Session Complete")
    logger.info("=" * 60)


@pytest.fixture(scope="session", autouse=True)
def initialize_slack_driver():
    """
    Initialize Slack driver at session start.

    This ensures the driver is ready before any tests run.
    Uses direct Slack SDK for simple, reliable integration.
    """
    from .utils.slack_driver import get_driver, cleanup_driver

    logger.info("🚀 Initializing Slack driver for test session...")

    try:
        driver = get_driver()
        logger.info("✅ Slack driver initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Slack driver: {e}")
        raise

    yield driver

    logger.info("🧹 Cleaning up Slack driver...")
    try:
        cleanup_driver()
        logger.info("✅ Slack driver cleaned up successfully")
    except Exception as e:
        logger.warning(f"⚠️  Error during cleanup: {e}")


# Make asyncio event loop available for session
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async operations"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

# Made with Bob
