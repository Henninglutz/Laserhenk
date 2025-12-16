"""LangGraph Workflow mit reduziertem KISS-Routing."""

import logging

from langgraph.graph import END, START, StateGraph

from workflow.graph_state import HenkGraphState
from workflow.nodes_kiss import route_node, run_step_node, validate_node

logger = logging.getLogger(__name__)


def _after_validate(state: HenkGraphState) -> str:
    return "route" if state.get("is_valid") else END


def _after_route(state: HenkGraphState) -> str:
    if state.get("awaiting_user_input"):
        return END
    return "run_step"


def _after_run_step(state: HenkGraphState) -> str:
    if state.get("awaiting_user_input"):
        return END
    next_step = state.get("next_step") or {}
    if next_step.get("should_continue"):
        return "run_step"
    return "route"


def create_smart_workflow() -> StateGraph:
    logger.info("[Workflow] Creating KISS workflow")

    workflow = StateGraph(HenkGraphState)

    workflow.add_node("validate", validate_node)
    workflow.add_node("route", route_node)
    workflow.add_node("run_step", run_step_node)

    workflow.add_edge(START, "validate")
    workflow.add_conditional_edges(
        "validate", _after_validate, {"route": "route", END: END}
    )
    workflow.add_conditional_edges(
        "route", _after_route, {"run_step": "run_step", END: END}
    )
    workflow.add_conditional_edges(
        "run_step", _after_run_step, {"run_step": "run_step", "route": "route", END: END}
    )

    return workflow.compile()
