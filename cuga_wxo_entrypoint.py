"""
WxO entry point for CUGA — Option 1: Native LangGraph Import.

WxO calls create_agent(config) at startup, then compiles the returned
StateGraph and manages checkpointing and LLM routing via its AI Gateway.

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

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph

from cuga.sdk import CugaAgent


def create_agent(config: RunnableConfig) -> StateGraph:
    """
    WxO-compatible factory function.

    Returns an UNCOMPILED StateGraph. WxO compiles it and manages
    checkpointing and the LLM via its AI Gateway.

    Args:
        config: RunnableConfig supplied by WxO at agent startup.
                Currently unused — LLM injection happens at the
                AI Gateway (network) level, not via RunnableConfig.

    Returns:
        Uncompiled LangGraph StateGraph ready for WxO to compile.
    """
    agent = CugaAgent()
    # _create_graph() returns the uncompiled HITL wrapper StateGraph.
    # Do NOT call agent.graph (property) — that compiles with MemorySaver,
    # which conflicts with WxO's own checkpointer.
    return agent._create_graph()
