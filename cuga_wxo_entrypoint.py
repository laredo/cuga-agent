"""
WxO entry point for CUGA — Option 1: Native LangGraph Import.

WxO calls create_agent(config) to get the StateGraph, then compiles it
and manages checkpointing. Credentials (OPENAI_API_KEY, AGENT_SETTING_CONFIG)
are injected by WxO via config["configurable"]["credentials"] after the
cuga_credentials connection is linked to the agent with:

    orchestrate agents experimental-connect -n cuga_agent -c cuga_credentials

The credential keys follow the WxO format: {app_id}_{field_name_lowercase}
e.g. cuga_credentials_openai_api_key, cuga_credentials_agent_setting_config

State schema
------------
WxO preserves only the `messages` field across turns. CUGA's AgentState
requires `input` (str) and `url` (str) as mandatory fields — WxO never
provides them. This entrypoint wraps CUGA's graph in a thin WxO-compatible
StateGraph whose state is just `messages`, then translates into/out of
AgentState in the single wrapper node.

The wrapper compiles CUGA's HITL graph WITHOUT a checkpointer so that
WxO can attach its own at the outer level. Full message history is forwarded
as `chat_messages` each turn so CUGA has conversation context.
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

    Reads credentials from config["configurable"]["credentials"], sets them
    as env vars for CUGA's settings loader, wraps CUGA's HITL graph in a
    WxO-compatible StateGraph, and returns it UNCOMPILED.

    Args:
        config: RunnableConfig supplied by WxO at agent startup — contains
                credentials under config["configurable"]["credentials"].

    Returns:
        Uncompiled LangGraph StateGraph ready for WxO to compile.
    """
    # ------------------------------------------------------------------
    # 1. Extract credentials from WxO config and inject as env vars so
    #    CUGA's dynaconf/TOML settings loader finds them normally.
    #    Key format: {app_id}_{field_name_lowercase}
    # ------------------------------------------------------------------
    credentials = (config or {}).get("configurable", {}).get("credentials", {})

    openai_api_key = (
        credentials.get(f"{APP_ID}_openai_api_key")
        or credentials.get(f"{APP_ID}_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    agent_setting_config = (
        credentials.get(f"{APP_ID}_agent_setting_config")
        or credentials.get(f"{APP_ID}_AGENT_SETTING_CONFIG")
        or os.environ.get("AGENT_SETTING_CONFIG", "settings.openai.toml")
    )

    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key
        logger.info("OPENAI_API_KEY loaded from WxO credentials")
    else:
        logger.warning("OPENAI_API_KEY not found in WxO credentials")

    os.environ.setdefault("AGENT_SETTING_CONFIG", agent_setting_config)

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

        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
        )
        input_text = last_human.content if last_human else ""

        cuga_input = AgentState(
            input=input_text,
            url="",
            chat_messages=list(messages),
            messages=[],
        ).model_dump()

        result = await compiled_cuga.ainvoke(cuga_input)

        # Priority 1: final_answer field (set by FinalAnswerNode)
        final_answer = result.get("final_answer", "")
        if final_answer:
            return {"messages": [AIMessage(content=str(final_answer))]}

        # Priority 2: last AIMessage in result["messages"] — may be JSON
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

        # Priority 3: last AIMessage in chat_messages
        result_chat: List[BaseMessage] = result.get("chat_messages") or []
        for m in reversed(result_chat):
            if isinstance(m, AIMessage) and m.content:
                return {"messages": [AIMessage(content=m.content)]}

        return {"messages": [AIMessage(content="I encountered an issue processing your request.")]}

    # ------------------------------------------------------------------
    # 4. Build and return the wrapper graph (UNCOMPILED — WxO compiles it).
    # ------------------------------------------------------------------
    workflow = StateGraph(WxOState)
    workflow.add_node("cuga", cuga_node)
    workflow.add_edge(START, "cuga")
    workflow.add_edge("cuga", END)
    return workflow
