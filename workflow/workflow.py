"""LangGraph Workflow mit reduziertem KISS-Routing."""

import logging

from langgraph.graph import END, START, StateGraph

from workflow.graph_state import HenkGraphState
from workflow.nodes_kiss import image_policy_node, route_node, run_step_node, validate_node

logger = logging.getLogger(__name__)


def _after_validate(state: HenkGraphState) -> str:
    return "route" if state.get("is_valid") else END


def _after_route(state: HenkGraphState) -> str:
    if state.get("awaiting_user_input"):
        return END
    return "image_policy"


def _after_image_policy(state: HenkGraphState) -> str:
    if state.get("awaiting_user_input"):
        return END
    return "run_step"


def _after_run_step(state: HenkGraphState) -> str:
    awaiting = state.get("awaiting_user_input")
    next_step = state.get("next_step") or {}

    logger.info(f"[Workflow] After run_step: awaiting_user_input={awaiting}, next_step={next_step}")

    if awaiting:
        logger.info("[Workflow] Awaiting user input, going to END")
        return END
    if next_step.get("should_continue"):
        logger.info(f"[Workflow] should_continue=True, going back to run_step for {next_step.get('name')}")
        return "run_step"
    logger.info("[Workflow] No continuation, going to route")
    return "route"


def create_smart_workflow() -> StateGraph:
    logger.info("[Workflow] Creating KISS workflow")

    workflow = StateGraph(HenkGraphState)

    workflow.add_node("validate", validate_node)
    workflow.add_node("route", route_node)
    workflow.add_node("image_policy", image_policy_node)
    workflow.add_node("run_step", run_step_node)

    workflow.add_edge(START, "validate")
    workflow.add_conditional_edges(
        "validate", _after_validate, {"route": "route", END: END}
    )
    workflow.add_conditional_edges(
        "route", _after_route, {"image_policy": "image_policy", END: END}
    )
    workflow.add_conditional_edges(
        "image_policy", _after_image_policy, {"run_step": "run_step", END: END}
    )
    workflow.add_conditional_edges(
        "run_step", _after_run_step, {"run_step": "run_step", "route": "route", END: END}
    )

    return workflow.compile()
