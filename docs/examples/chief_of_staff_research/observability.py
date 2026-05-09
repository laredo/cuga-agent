"""Observability setup for the chief_of_staff_research swarm.

Initialises:
  - A loguru file sink writing to logs/swarm.log
  - ToolCallLoggingCallback: logs every tool call to swarm.log (and dashboard)
  - Langfuse LangChain callback handler (if credentials present in env)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from loguru import logger

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "swarm.log"


# ---------------------------------------------------------------------------
# Tool call logging callback (always active — no external credentials needed)
# ---------------------------------------------------------------------------

class ToolCallLoggingCallback:
    """LangChain BaseCallbackHandler that writes tool calls to loguru.

    Compatible with both langchain_core and legacy langchain callback APIs.
    Tags passed via ``config={"tags": [agent_id]}`` are surfaced as the agent
    label so per-agent filtering in the dashboard works.
    """

    def _agent_label(self, kwargs: Dict[str, Any]) -> str:
        tags: List[str] = kwargs.get("tags") or []
        return tags[0] if tags else "?"

    # -- tool events ---------------------------------------------------------

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        name = serialized.get("name") or serialized.get("id", ["?"])[-1]
        label = (tags or ["?"])[0]
        # Trim long inputs so the log stays readable
        preview = input_str[:300].replace("\n", " ")
        logger.info(f"[tool:{label}] ▶ {name}  input={preview!r}")

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        label = (tags or ["?"])[0]
        preview = str(output)[:300].replace("\n", " ")
        logger.info(f"[tool:{label}] ◀ {preview!r}")

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        label = (tags or ["?"])[0]
        logger.warning(f"[tool:{label}] ✗ {error}")

    # -- LLM events ----------------------------------------------------------

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        label = (tags or ["?"])[0]
        model = serialized.get("name") or serialized.get("id", ["?"])[-1]
        logger.debug(f"[llm:{label}] ▶ {model}  ({len(prompts)} prompt(s))")

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: UUID = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        label = (tags or ["?"])[0]
        model = serialized.get("name") or serialized.get("id", ["?"])[-1]
        n_msgs = sum(len(m) for m in messages)
        logger.debug(f"[llm:{label}] ▶ {model}  ({n_msgs} message(s))")

    def on_llm_end(self, response: Any, *, run_id: UUID = None, tags: Optional[List[str]] = None, **kwargs: Any) -> None:
        pass  # individual tool-end events are sufficient

    # satisfy LangChain's duck-typing check
    def __repr__(self) -> str:
        return "ToolCallLoggingCallback()"


# ---------------------------------------------------------------------------
# Langfuse (optional — set env vars to enable)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Swarm log file sink
# ---------------------------------------------------------------------------

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
