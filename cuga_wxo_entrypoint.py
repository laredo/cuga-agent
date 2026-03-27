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

State schema
------------
WxO preserves only the `messages` field across turns.  CUGA's AgentState
requires `input` (str) and `url` (str) as mandatory fields — WxO never
provides them.  This entrypoint wraps CUGA's graph in a thin WxO-
compatible StateGraph whose state is just `messages`, then translates
into/out of AgentState in the single wrapper node.

The wrapper compiles CUGA's HITL graph WITHOUT a checkpointer so that
WxO can attach its own at the outer level.  Full message history is
forwarded as `chat_messages` each turn so CUGA has conversation context.

Checkpointer note
-----------------
CugaAgent._create_graph() returns the UNCOMPILED StateGraph wrapper.
The compiled graph (with MemorySaver) lives on CugaAgent.graph — we
deliberately avoid that property here so WxO can attach its own
checkpointer at compile time.
"""

import json
import os
from typing import Annotated, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from loguru import logger
from typing_extensions import TypedDict

APP_ID = "cuga_credentials"


class WxOState(TypedDict):
    """Minimal WxO-compatible state — only `messages` is preserved between turns."""

    messages: Annotated[List[BaseMessage], add_messages]


def create_agent(config: RunnableConfig) -> StateGraph:
    """
    WxO-compatible factory function.

    Loads CUGA credentials from the WxO key_value connection into env vars,
    wraps CUGA's HITL graph in a WxO-compatible StateGraph, and returns it
    UNCOMPILED so WxO can attach its own checkpointer.

    Args:
        config: RunnableConfig supplied by WxO at agent startup.

    Returns:
        Uncompiled LangGraph StateGraph ready for WxO to compile.
    """
    # ------------------------------------------------------------------
    # 1. Inject WxO connection credentials as env vars so CUGA's settings
    #    loader (dynaconf / TOML) finds them the same way it does locally.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 2. Build CUGA agent and compile its inner HITL graph WITHOUT a
    #    checkpointer (WxO provides the outer one via the wrapper graph).
    # ------------------------------------------------------------------
    from cuga.backend.cuga_graph.state.agent_state import AgentState
    from cuga.sdk import CugaAgent

    agent = CugaAgent()
    cuga_inner_graph = agent._create_graph()
    compiled_cuga = cuga_inner_graph.compile()  # no checkpointer — WxO manages state

    # ------------------------------------------------------------------
    # 3. Wrapper node: translates WxO state ↔ CUGA AgentState.
    # ------------------------------------------------------------------
    async def cuga_node(state: WxOState, node_config: RunnableConfig):
        messages: List[BaseMessage] = state["messages"]

        # Extract the latest human message as the `input` field CUGA requires.
        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
        )
        input_text = last_human.content if last_human else ""

        # Build a valid AgentState: required fields get safe defaults;
        # full message history is forwarded as chat_messages for context.
        cuga_input = AgentState(
            input=input_text,
            url="",
            chat_messages=list(messages),
            messages=[],
        ).model_dump()

        # Invoke CUGA (single turn — full state passed explicitly each turn).
        result = await compiled_cuga.ainvoke(cuga_input)

        # ------------------------------------------------------------------
        # 4. Extract CUGA's response and convert to a WxO AIMessage.
        # ------------------------------------------------------------------
        # Priority 1: structured final_answer field (set by FinalAnswerNode).
        final_answer = result.get("final_answer", "")
        if final_answer:
            return {"messages": [AIMessage(content=str(final_answer))]}

        # Priority 2: last AIMessage in result["messages"] — may be JSON from
        # FinalAnswerNode: {"thoughts": [...], "final_answer": "...", ...}
        result_messages: List[BaseMessage] = result.get("messages") or []
        for m in reversed(result_messages):
            if isinstance(m, AIMessage) and m.content:
                try:
                    parsed = json.loads(m.content)
                    if "final_answer" in parsed:
                        return {"messages": [AIMessage(content=str(parsed["final_answer"]))]}
                except (json.JSONDecodeError, TypeError):
                    pass
                return {"messages": [AIMessage(content=m.content)]}

        # Priority 3: last AIMessage in chat_messages.
        result_chat: List[BaseMessage] = result.get("chat_messages") or []
        for m in reversed(result_chat):
            if isinstance(m, AIMessage) and m.content:
                return {"messages": [AIMessage(content=m.content)]}

        return {"messages": [AIMessage(content="I encountered an issue processing your request.")]}

    # ------------------------------------------------------------------
    # 5. Build and return the wrapper graph (UNCOMPILED — WxO compiles it).
    # ------------------------------------------------------------------
    workflow = StateGraph(WxOState)
    workflow.add_node("cuga", cuga_node)
    workflow.add_edge(START, "cuga")
    workflow.add_edge("cuga", END)
    return workflow
