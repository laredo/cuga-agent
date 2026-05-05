"""
Test API Server for Tavern Tests

Simple Flask server that wraps the Slack driver for use with Tavern's
standard HTTP request format. This bypasses Tavern's schema validation issues.

Usage:
    python test_api_server.py

The server will start on http://localhost:5555
"""

import os
from pathlib import Path
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from loguru import logger

# Load environment
env_file = Path(__file__).parent / ".env"
load_dotenv(env_file)

# Import Slack driver
from utils.slack_driver import SlackDriver

# Initialize Flask app
app = Flask(__name__)

# Initialize Slack driver
bot_token = os.getenv("TEST_DRIVER_SLACK_BOT_TOKEN")
target_bot_user_id = os.getenv("CUGA_BOT_USER_ID")

if not bot_token:
    raise ValueError("TEST_DRIVER_SLACK_BOT_TOKEN must be set")

driver = SlackDriver(bot_token, target_bot_user_id)
driver.initialize()

logger.info(f"✅ Test API Server initialized with bot_id: {driver.bot_user_id}")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "bot_id": driver.bot_user_id
    })


@app.route('/slack/send', methods=['POST'])
def slack_send():
    """
    Send message to Slack.

    Request body:
        {
            "channel": "C0AKFDWC9JS",
            "text": "Hello world",
            "thread_ts": "1234567890.123456"  // optional
        }

    Response:
        {
            "ts": "1234567890.123456",
            "channel": "C0AKFDWC9JS",
            "text": "Hello world"
        }
    """
    try:
        data = request.json
        channel = data.get('channel')
        text = data.get('text')
        thread_ts = data.get('thread_ts')

        if not channel or not text:
            return jsonify({"error": "channel and text are required"}), 400

        result = driver.send_message(channel, text, thread_ts)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in /slack/send: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/slack/wait', methods=['POST'])
def slack_wait():
    """
    Wait for bot response.

    Request body:
        {
            "channel": "C0AKFDWC9JS",
            "thread_ts": "1234567890.123456",  // optional
            "timeout": 30  // optional, default 30
        }

    Response:
        {
            "text": "Bot response",
            "user": "U0AKZPAEJRL",
            "ts": "1234567890.123457",
            "thread_ts": "1234567890.123456"
        }
    """
    try:
        data = request.json
        channel = data.get('channel')
        thread_ts = data.get('thread_ts')
        timeout = data.get('timeout', 30)

        if not channel:
            return jsonify({"error": "channel is required"}), 400

        response = driver.wait_for_response(channel=channel, after_ts=thread_ts, thread_ts=thread_ts, timeout=timeout)

        if response is None:
            return jsonify({"error": "Timeout waiting for response"}), 408

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error in /slack/wait: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/slack/send_and_wait', methods=['POST'])
def slack_send_and_wait():
    """
    Send message and wait for bot response.

    Request body:
        {
            "channel": "C0AKFDWC9JS",
            "text": "Hello bot",
            "thread_ts": "1234567890.123456",  // optional - send in thread
            "timeout": 30  // optional, default 30
        }

    Response:
        {
            "sent": {
                "ts": "1234567890.123456",
                "channel": "C0AKFDWC9JS",
                "text": "Hello bot"
            },
            "response": {
                "text": "Bot response",
                "user": "U0AKZPAEJRL",
                "ts": "1234567890.123457",
                "thread_ts": "1234567890.123456"
            }
        }
    """
    try:
        data = request.json
        channel = data.get('channel')
        text = data.get('text')
        thread_ts = data.get('thread_ts')
        timeout = data.get('timeout', 30)

        if not channel or not text:
            return jsonify({"error": "channel and text are required"}), 400

        sent, response = driver.send_and_wait(channel, text, thread_ts=thread_ts, timeout=timeout)

        if response is None:
            return jsonify({
                "sent": sent,
                "response": None,
                "error": "Timeout waiting for response"
            }), 408

        return jsonify({
            "sent": sent,
            "response": response
        }), 200

    except Exception as e:
        logger.error(f"Error in /slack/send_and_wait: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/slack/get_thread', methods=['POST'])
def slack_get_thread():
    """
    Get all messages in a thread.

    Request body:
        {
            "channel": "C0AKFDWC9JS",
            "thread_ts": "1234567890.123456"
        }

    Response:
        {
            "messages": [...]
        }
    """
    try:
        data = request.json
        channel = data.get('channel')
        thread_ts = data.get('thread_ts')

        if not channel or not thread_ts:
            return jsonify({"error": "channel and thread_ts are required"}), 400

        messages = driver.get_thread_messages(channel, thread_ts)
        return jsonify({"messages": messages}), 200

    except Exception as e:
        logger.error(f"Error in /slack/get_thread: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/slack/react', methods=['POST'])
def slack_react():
    """
    Add a reaction to a Slack message.

    Request body:
        {
            "channel": "C0AKFDWC9JS",
            "timestamp": "1234567890.123456",
            "reaction": "+1"
        }

    Response:
        {
            "channel": "C0AKFDWC9JS",
            "timestamp": "1234567890.123456",
            "reaction": "+1"
        }
    """
    try:
        data = request.json
        channel = data.get('channel')
        timestamp = data.get('timestamp')
        reaction = data.get('reaction')

        if not channel or not timestamp or not reaction:
            return jsonify({"error": "channel, timestamp, and reaction are required"}), 400

        result = driver.add_reaction(channel, timestamp, reaction)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in /slack/react: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/slack/react_and_wait', methods=['POST'])
def slack_react_and_wait():
    """
    Add a reaction to a message and wait for the bot to respond in that thread.

    Request body:
        {
            "channel": "C0AKFDWC9JS",
            "message_ts": "1234567890.123456",
            "reaction": "+1",
            "timeout": 30
        }

    Response:
        {
            "reaction": {"channel": "...", "timestamp": "...", "reaction": "+1"},
            "response": {"text": "approved", "user": "...", "ts": "...", "thread_ts": "..."}
        }
    """
    try:
        data = request.json
        channel = data.get('channel')
        message_ts = data.get('message_ts')
        reaction = data.get('reaction')
        timeout = data.get('timeout', 30)

        if not channel or not message_ts or not reaction:
            return jsonify({"error": "channel, message_ts, and reaction are required"}), 400

        reaction_info, response = driver.react_and_wait(
            channel=channel,
            message_ts=message_ts,
            reaction=reaction,
            timeout=timeout,
        )

        if response is None:
            return jsonify({
                "reaction": reaction_info,
                "response": None,
                "error": "Timeout waiting for bot response",
            }), 408

        return jsonify({"reaction": reaction_info, "response": response}), 200

    except Exception as e:
        logger.error(f"Error in /slack/react_and_wait: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("🚀 Starting Test API Server on http://localhost:5555")
    logger.info("📝 Endpoints:")
    logger.info("  GET  /health")
    logger.info("  POST /slack/send")
    logger.info("  POST /slack/wait")
    logger.info("  POST /slack/send_and_wait")
    logger.info("  POST /slack/get_thread")
    logger.info("  POST /slack/react")
    logger.info("  POST /slack/react_and_wait")

    app.run(host='0.0.0.0', port=5555, debug=False)

# Made with Bob
