"""LangGraph workflow for fabric-first rendering."""

from __future__ import annotations

from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from agents.render_patch_agent import RenderPatchAgent
from models.rendering import PatchDecision, ProductParameters, RenderRequest, RenderResult
from tools.dalle_tool import DALLETool
from tools.rendering_patch import apply_patch


class RenderGraphState(TypedDict, total=False):
    session_id: str
    render_request: RenderRequest
    render_result: Optional[RenderResult]
    user_message: Optional[str]
    product_params: ProductParameters
    notes_for_prompt: list[str]
    patch_decision: Optional[PatchDecision]
    clarifying_question: Optional[str]
    rag_style_context: Optional[str]


async def _decide_patch(state: RenderGraphState) -> RenderGraphState:
    user_message = state.get("user_message") or ""
    params = state["product_params"]
    rag_style_context = state.get("rag_style_context")
    decision = await RenderPatchAgent().extract_patch_decision(
        user_message=user_message,
        params=params,
        rag_style_context=rag_style_context,
    )
    return {
        "patch_decision": decision,
        "notes_for_prompt": decision.notes_for_prompt,
        "clarifying_question": decision.clarifying_question,
    }


async def _apply_patch_node(state: RenderGraphState) -> RenderGraphState:
    decision = state.get("patch_decision")
    if not decision or decision.intent != "update_render_params" or not decision.patch:
        return {}
    updated = apply_patch(state["product_params"], decision.patch)
    return {"product_params": updated}


async def _render_node(state: RenderGraphState) -> RenderGraphState:
    if state.get("clarifying_question"):
        return {"render_result": None}

    request = state["render_request"]
    if state.get("product_params"):
        request = request.model_copy(update={"params": state["product_params"]})

    notes = state.get("notes_for_prompt") or []
    result = await DALLETool().generate_product_sheet(request, notes_for_prompt=notes)
    return {"render_result": result}


def create_rendering_workflow() -> StateGraph:
    workflow = StateGraph(RenderGraphState)

    workflow.add_node("decide_patch", _decide_patch)
    workflow.add_node("apply_patch", _apply_patch_node)
    workflow.add_node("render", _render_node)

    workflow.add_edge(START, "decide_patch")
    workflow.add_edge("decide_patch", "apply_patch")
    workflow.add_edge("apply_patch", "render")
    workflow.add_edge("render", END)

    return workflow.compile()
