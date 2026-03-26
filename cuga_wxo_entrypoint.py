"""
WxO entry point for CUGA — Option 1: Native LangGraph Import.

WxO calls create_agent(config) to get the StateGraph, then compiles it
and manages checkpointing. CUGA's runtime credentials (LLM API key,
model TOML config, etc.) are supplied via a WxO key_value connection
named 'cuga_credentials', which the entrypoint injects as env vars so
CUGA's internal settings loader finds them normally.

Setup (one-time, per environment):
    orchestrate connections add -a cuga_credentials
    orchestrate connections configure -a cuga_credentials \
        --env draft --kind key_value --type team
    orchestrate connections set-credentials -a cuga_credentials \
        --env draft \
        -e OPENAI_API_KEY=sk-... \
        -e AGENT_SETTING_CONFIG=settings.openai.toml

State persistence note
----------------------
WxO only preserves the `messages` field across turns. CUGA's primary
conversation field is `chat_messages`. Non-message fields (policies,
trajectory, pending_approvals) are re-initialised each turn (Option A —
stateless-per-turn policy evaluation). See cuga_wxo_option1.md §Change 2
for Option B (serialise state into a hidden system message).

Checkpointer note
-----------------
CugaAgent._create_graph() returns the UNCOMPILED StateGraph wrapper.
The compiled graph (with MemorySaver) lives on CugaAgent.graph — we
deliberately avoid that property here so WxO can attach its own
checkpointer at compile time.
"""

import os

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from loguru import logger

APP_ID = "cuga_credentials"


def create_agent(config: RunnableConfig) -> StateGraph:
    """
    WxO-compatible factory function.

    Loads CUGA credentials from the WxO key_value connection into env vars,
    then builds and returns an UNCOMPILED StateGraph for WxO to compile.

    Args:
        config: RunnableConfig supplied by WxO at agent startup.

    Returns:
        Uncompiled LangGraph StateGraph ready for WxO to compile.
    """
    # Inject WxO connection credentials as env vars so CUGA's settings
    # loader (dynaconf / TOML) finds them the same way it does locally.
    try:
        from ibm_watsonx_orchestrate.run import connections
        creds = connections.key_value(APP_ID)
        for key, value in creds.items():
            os.environ.setdefault(key, value)
        logger.info(f"Loaded {len(creds)} credential(s) from WxO connection '{APP_ID}'")
    except Exception as e:
        logger.warning(
            f"Could not load WxO connection '{APP_ID}': {e} — "
            "assuming env vars are already set (local dev mode)"
        )

    from cuga.sdk import CugaAgent
    agent = CugaAgent()
    # _create_graph() returns the uncompiled HITL wrapper StateGraph.
    # Do NOT call agent.graph (property) — that compiles with MemorySaver,
    # which conflicts with WxO's own checkpointer.
    return agent._create_graph()
