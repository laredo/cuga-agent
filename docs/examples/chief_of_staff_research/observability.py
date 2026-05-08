"""Observability setup for the chief_of_staff_research swarm.

Initialises:
  - Langfuse LangChain callback handler (if credentials present in env)
  - A loguru file sink writing to logs/swarm.log
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

from loguru import logger

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "swarm.log"


def setup_langfuse() -> Optional[Any]:
    """Return a configured Langfuse CallbackHandler, or None if unavailable."""
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        logger.warning("LANGFUSE_PUBLIC_KEY not set — Langfuse tracing disabled")
        return None

    try:
        try:
            from langfuse.langchain import CallbackHandler
        except ImportError:
            from langfuse.callback.langchain import LangchainCallbackHandler as CallbackHandler

        handler = CallbackHandler()
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        logger.info(f"Langfuse tracing enabled → {host}")
        return handler

    except Exception as exc:
        logger.warning(f"Langfuse init failed ({exc}) — tracing disabled")
        return None


def setup_swarm_logging() -> Path:
    """Add a rotating file sink for the combined swarm log. Returns log path."""
    LOG_DIR.mkdir(exist_ok=True)
    logger.add(
        LOG_FILE,
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
    )
    logger.info(f"Swarm log → {LOG_FILE}")
    return LOG_FILE
