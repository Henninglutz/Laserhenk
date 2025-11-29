"""LangGraph Workflow for HENK Agent System."""

from typing import Literal

from langgraph.graph import StateGraph, END

from agents.henk1 import Henk1Agent
from agents.operator import OperatorAgent
from agents.design_henk import DesignHenkAgent
from agents.laserhenk import LaserHenkAgent
from models.graph_state import HenkGraphState
from tools.rag_tool import RAGTool


def _add_message(state: HenkGraphState, role: str, content: str, sender: str):
    """Helper to add message to state."""
    state["messages"].append({
        "role": role,
        "content": content,
        "sender": sender
    })


async def rag_tool_node(state: HenkGraphState) -> HenkGraphState:
    """RAG Tool Node - PostgreSQL Database Queries."""
    print("=== RAG_TOOL_NODE CALLED ===")
    print(f"    action_params: {state.get('action_params')}")
    print(f"    BEFORE: rag_context = {state['session_state'].rag_context}")

    rag_tool = RAGTool()
    query_text = state.get("action_params", {}).get("query", "")

    from models.tools import RAGQuery
    query = RAGQuery(query=query_text, top_k=5)
    result = await rag_tool.query(query)

    # Store result
    state["rag_output"] = {"results": result.results, "metadata": result.metadata}
    state["session_state"].rag_context = result.results

    print(f"    AFTER: rag_context = {state['session_state'].rag_context}")
    print(f"    Results count: {len(result.results)}")

    _add_message(state, "system", f"[RAG] Retrieved {len(result.results)} results", "rag_tool")

    # Clear pending action
    state["pending_action"] = None
    state["action_params"] = None

    print("=== RAG_TOOL_NODE COMPLETED ===")
    return state


async def henk1_node(state: HenkGraphState) -> HenkGraphState:
    """HENK1 Agent Node."""
    print(f"=== HENK1_NODE CALLED ===")
    agent = Henk1Agent()
    decision = await agent.process(state["session_state"])

    # Update state based on decision
    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    if decision.message:
        _add_message(state, "assistant", decision.message, "henk1")

    print(f"=== HENK1_NODE: next_agent = {decision.next_agent}, action = {decision.action}")
    return state


async def operator_node(state: HenkGraphState) -> HenkGraphState:
    """Operator Agent Node."""
    print(f"=== OPERATOR_NODE CALLED ===")
    agent = OperatorAgent()
    decision = await agent.process(state["session_state"])

    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    if decision.message:
        _add_message(state, "system", decision.message, "operator")

    print(f"=== OPERATOR_NODE: next_agent = {decision.next_agent}, action = {decision.action}")
    return state


async def design_henk_node(state: HenkGraphState) -> HenkGraphState:
    """Design HENK Agent Node."""
    print(f"=== DESIGN_HENK_NODE CALLED ===")
    agent = DesignHenkAgent()
    decision = await agent.process(state["session_state"])

    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    if decision.message:
        _add_message(state, "assistant", decision.message, "design_henk")

    print(f"=== DESIGN_HENK_NODE: next_agent = {decision.next_agent}, action = {decision.action}")
    return state


async def laserhenk_node(state: HenkGraphState) -> HenkGraphState:
    """LASERHENK Agent Node."""
    print(f"=== LASERHENK_NODE CALLED ===")
    agent = LaserHenkAgent()
    decision = await agent.process(state["session_state"])

    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action
    state["action_params"] = decision.action_params

    if decision.message:
        _add_message(state, "assistant", decision.message, "laserhenk")

    print(f"=== LASERHENK_NODE: next_agent = {decision.next_agent}, action = {decision.action}")
    return state


def route_after_agent(state: HenkGraphState) -> Literal["operator", "henk1", "design_henk", "laserhenk", "rag_tool", "end"]:
    """Route to next node based on pending action or next agent."""
    print(f"=== ROUTING: pending_action = {state.get('pending_action')}, next_agent = {state.get('next_agent')}")

    # If there's a pending action, route to the tool
    if state.get("pending_action") == "query_rag":
        print("=== ROUTING TO: rag_tool")
        return "rag_tool"

    # Otherwise route to next agent
    next_agent = state.get("next_agent")

    if next_agent == "henk1":
        print("=== ROUTING TO: henk1")
        return "henk1"
    elif next_agent == "operator":
        print("=== ROUTING TO: operator")
        return "operator"
    elif next_agent == "design_henk":
        print("=== ROUTING TO: design_henk")
        return "design_henk"
    elif next_agent == "laserhenk":
        print("=== ROUTING TO: laserhenk")
        return "laserhenk"
    else:
        print("=== ROUTING TO: end")
        return "end"


def create_workflow() -> StateGraph:
    """Create the LangGraph workflow."""
    workflow = StateGraph(HenkGraphState)

    # Add nodes
    workflow.add_node("operator", operator_node)
    workflow.add_node("henk1", henk1_node)
    workflow.add_node("design_henk", design_henk_node)
    workflow.add_node("laserhenk", laserhenk_node)
    workflow.add_node("rag_tool", rag_tool_node)

    # Set entry point
    workflow.set_entry_point("operator")

    # Define path mapping for routing
    path_map = {
        "operator": "operator",
        "henk1": "henk1",
        "design_henk": "design_henk",
        "laserhenk": "laserhenk",
        "rag_tool": "rag_tool",
        "end": END,
    }

    # Add conditional edges from each agent node
    workflow.add_conditional_edges("operator", route_after_agent, path_map)
    workflow.add_conditional_edges("henk1", route_after_agent, path_map)
    workflow.add_conditional_edges("design_henk", route_after_agent, path_map)
    workflow.add_conditional_edges("laserhenk", route_after_agent, path_map)

    # RAG tool always routes back to operator
    workflow.add_edge("rag_tool", "operator")

    return workflow.compile()
