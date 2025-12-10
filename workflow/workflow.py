"""
LangGraph Workflow mit Smart Supervisor

Definiert den kompletten Workflow-Graph mit intelligentem Routing.

Flow:
START → validate_query → smart_operator → [conversation | tools] → smart_operator → ...
"""

from langgraph.graph import StateGraph, START, END
from workflow.graph_state import HenkGraphState
from workflow.nodes import (
    validate_query_node,
    smart_operator_node,
    conversation_node,
    tools_dispatcher_node,
)
import logging

logger = logging.getLogger(__name__)


def should_continue_after_operator(state: HenkGraphState) -> str:
    """
    Routing-Logik nach Smart Operator.

    Entscheidet basierend auf next_agent wohin es geht:
    - "conversation": Zu Agent (henk1, design_henk, laserhenk)
    - "tools": Zu Tool (rag_tool, comparison_tool, pricing_tool)
    - END: Gespräch beenden oder auf User warten

    Args:
        state: Aktueller Graph State

    Returns:
        String: "conversation", "tools", oder END
    """
    next_dest = state.get("next_agent")

    if next_dest == "end":
        logger.info("[Router] Ending conversation (user signaled end)")
        return END

    elif next_dest == "clarification":
        logger.info("[Router] Waiting for user clarification")
        return END

    elif next_dest in ["rag_tool", "comparison_tool", "pricing_tool"]:
        logger.info(f"[Router] Routing to tool: {next_dest}")
        return "tools"

    elif next_dest in ["henk1", "design_henk", "laserhenk"]:
        logger.info(f"[Router] Routing to agent: {next_dest}")
        return "conversation"

    else:
        logger.warning(f"[Router] Unknown destination '{next_dest}', defaulting to END")
        return END


def should_continue_after_conversation(state: HenkGraphState) -> str:
    """
    Routing-Logik nach Conversation.

    Entscheidet ob:
    - Zu Tool (wenn Agent tool anfordert)
    - Zurück zu Operator (für nächste Entscheidung)
    - END (User-Input benötigt)

    Args:
        state: Aktueller Graph State

    Returns:
        String: "tools", "smart_operator" oder END
    """
    awaiting_input = state.get("awaiting_user_input", False)
    next_dest = state.get("next_agent")

    if awaiting_input:
        logger.info("[Router] Awaiting user input, ending turn")
        return END

    # Check if agent requested a tool
    if next_dest in ["rag_tool", "comparison_tool", "pricing_tool"]:
        logger.info(f"[Router] Agent requested tool: {next_dest}, routing to tools")
        return "tools"

    # Sonst: Zurück zu Operator für nächste Entscheidung
    logger.info("[Router] Returning to operator for next decision")
    return "smart_operator"


def should_continue_after_tools(state: HenkGraphState) -> str:
    """
    Routing-Logik nach Tool Execution.

    Entscheidet ob:
    - Zurück zum Agent der das Tool angefordert hat (conversation)
    - END (User-Input benötigt)

    Args:
        state: Aktueller Graph State

    Returns:
        String: "conversation" oder END
    """
    awaiting_input = state.get("awaiting_user_input", False)
    next_dest = state.get("next_agent")

    if awaiting_input:
        logger.info("[Router] After tools: Awaiting user input, ending turn")
        return END

    # Return to the agent that requested the tool
    if next_dest in ["henk1", "design_henk", "laserhenk"]:
        logger.info(f"[Router] After tools: Returning to agent '{next_dest}'")
        return "conversation"

    # No agent to return to, wait for user
    logger.info("[Router] After tools: No agent specified, ending turn")
    return END


def create_smart_workflow() -> StateGraph:
    """
    Erstellt den Workflow mit intelligentem Supervisor.

    Der Workflow implementiert ein Feedback-Loop System:
    1. User Input wird validiert
    2. Supervisor entscheidet wohin (Agent/Tool)
    3. Agent/Tool wird ausgeführt
    4. Zurück zu Supervisor für nächste Entscheidung
    5. Repeat bis END

    Returns:
        Kompilierter StateGraph ready für Execution

    Example:
        >>> workflow = create_smart_workflow()
        >>> result = await workflow.ainvoke(initial_state)
    """
    logger.info("[Workflow] Creating Smart Workflow with Supervisor")

    workflow = StateGraph(HenkGraphState)

    # ==================== Add Nodes ====================
    workflow.add_node("validate_query", validate_query_node)
    workflow.add_node("smart_operator", smart_operator_node)
    workflow.add_node("conversation", conversation_node)
    workflow.add_node("tools", tools_dispatcher_node)

    logger.info(
        "[Workflow] Nodes added: validate_query, smart_operator, conversation, tools"
    )

    # ==================== Add Edges ====================

    # START → validate_query (Entry Point)
    workflow.add_edge(START, "validate_query")

    # validate_query → smart_operator OR END
    workflow.add_conditional_edges(
        "validate_query",
        lambda state: "smart_operator" if state.get("is_valid") else END,
        {"smart_operator": "smart_operator", END: END},
    )

    # smart_operator → conversation OR tools OR END
    workflow.add_conditional_edges(
        "smart_operator",
        should_continue_after_operator,
        {"conversation": "conversation", "tools": "tools", END: END},
    )

    # conversation → tools OR smart_operator OR END (Feedback-Loop!)
    workflow.add_conditional_edges(
        "conversation",
        should_continue_after_conversation,
        {"tools": "tools", "smart_operator": "smart_operator", END: END},
    )

    # tools → conversation OR END (return to agent that requested tool, OR wait for user)
    workflow.add_conditional_edges(
        "tools",
        should_continue_after_tools,
        {"conversation": "conversation", END: END},
    )

    logger.info("[Workflow] Edges configured with feedback loops")

    # ==================== Compile ====================
    compiled = workflow.compile()

    logger.info("[Workflow] Smart Workflow compiled successfully")

    return compiled
