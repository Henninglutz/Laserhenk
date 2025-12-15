"""Kompakte KISS-Workflow-Nodes mit strukturierten Actions."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from agents.henk1 import Henk1Agent
from agents.design_henk import DesignHenkAgent
from agents.laserhenk import LaserHenkAgent
from agents.operator import OperatorAgent
from models.customer import SessionState
from models.handoff import (
    DesignHenkToLaserHenkPayload,
    HandoffValidator,
    Henk1ToDesignHenkPayload,
    LaserHenkToHITLPayload,
)
from tools.dalle_tool import DALLETool
from models.tools import DALLEImageRequest
from tools.fabric_preferences import build_fabric_search_criteria
from tools.rag_tool import RAGTool
from workflow.graph_state import HenkGraphState

logger = logging.getLogger(__name__)


class HandoffAction(BaseModel):
    kind: str = Field(description="agent | tool | end | clarification")
    name: str = Field(description="Agent- oder Tool-Name")
    params: dict = Field(default_factory=dict)
    user_message: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    should_continue: bool = True
    return_to_agent: Optional[str] = None


class ToolResult(BaseModel):
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


AGENT_REGISTRY: Dict[str, Callable[[], Any]] = {
    "henk1": Henk1Agent,
    "design_henk": DesignHenkAgent,
    "laserhenk": LaserHenkAgent,
    "operator": OperatorAgent,
}


def _session_state(state: HenkGraphState) -> SessionState:
    session_state = state.get("session_state")
    return session_state if isinstance(session_state, SessionState) else SessionState(**(session_state or {}))


async def _rag_tool(params: dict, state: HenkGraphState) -> ToolResult:
    session_state = _session_state(state)

    query = params.get("query") or params.get("prompt") or ""
    if not query:
        return ToolResult(text="Ich brauche noch ein paar Details für die Stoffsuche.")

    criteria, updated_state, _, _ = build_fabric_search_criteria(query, params, session_state)
    session_state = updated_state or session_state

    recommendations = await RAGTool().search_fabrics(criteria)
    fabrics = []
    for rec in recommendations[:10]:
        fabric = getattr(rec, "fabric", None)
        fabrics.append(fabric.model_dump() if fabric and hasattr(fabric, "model_dump") else (fabric or {}))
    session_state.rag_context = {"fabrics": fabrics, "query": query}

    fabric_images = []
    for rec in recommendations[:2]:
        fabric = rec.fabric
        code = fabric.fabric_code.replace("/", "_") if fabric.fabric_code else "fabric"
        fabric_images.append({
            "url": f"/fabrics/images/{code}.jpg",
            "fabric_code": fabric.fabric_code,
            "name": fabric.name,
            "color": fabric.color,
            "pattern": fabric.pattern,
        })

    if hasattr(session_state, "shown_fabric_images"):
        session_state.shown_fabric_images.extend(fabric_images)

    state["session_state"] = session_state

    formatted_lines = []
    for idx, rec in enumerate(recommendations[:5], 1):
        fabric = getattr(rec, "fabric", None)
        formatted_lines.append(
            f"{idx}. {getattr(fabric, 'name', None) or 'Hochwertiger Stoff'} (Code: {getattr(fabric, 'fabric_code', None)}) - "
            f"Farbe: {getattr(fabric, 'color', None) or 'klassisch'}, Muster: {getattr(fabric, 'pattern', None) or 'uni'}\n"
        )
    formatted = "**Passende Stoffe für dich:**\n\n" + "".join(formatted_lines)

    metadata: Dict[str, Any] = {"fabric_images": fabric_images} if fabric_images else {}
    return ToolResult(text=formatted, metadata=metadata)


async def _dalle_tool(params: dict, state: HenkGraphState) -> ToolResult:
    session_state = _session_state(state)

    prompt = params.get("prompt") or "Mood Board für ein elegantes Outfit"
    request = params.get("request")
    request = request if isinstance(request, DALLEImageRequest) else DALLEImageRequest(prompt=prompt)

    response = await DALLETool().generate_image(request=request)
    image_url = getattr(response, "image_url", None)
    if image_url:
        session_state.mood_image_url = image_url
        session_state.image_generation_history.append({"image_url": image_url, "type": "dalle"})
        state["session_state"] = session_state

    text = response.error if getattr(response, "error", None) else "Hier ist dein Mood Board!"
    metadata = {"image_url": image_url} if image_url else {}
    return ToolResult(text=text, metadata=metadata)


async def _mark_favorite_fabric(params: dict, state: HenkGraphState) -> ToolResult:
    session_state = _session_state(state)

    fabric_code = params.get("fabric_code")
    if not fabric_code:
        return ToolResult(text="Welchen Stoff möchtest du als Favoriten markieren?")

    fabric = next(
        (item for item in getattr(session_state, "shown_fabric_images", []) if item.get("fabric_code") == fabric_code),
        None,
    )

    if fabric:
        session_state.favorite_fabric = fabric
        state["session_state"] = session_state
        return ToolResult(text=f"Alles klar, Stoff {fabric_code} ist jetzt dein Favorit.", metadata={"favorite_fabric": fabric})

    return ToolResult(text="Ich habe diesen Stoff leider nicht gefunden.")


TOOL_REGISTRY: Dict[str, Callable[[dict, HenkGraphState], Any]] = {
    "rag_tool": _rag_tool,
    "dalle_mood_board": _dalle_tool,
    "dalle_tool": _dalle_tool,
    "mark_favorite_fabric": _mark_favorite_fabric,
}


async def validate_node(state: HenkGraphState) -> HenkGraphState:
    messages = list(state.get("messages", []))
    content = next((m.get("content", "").strip() for m in reversed(messages) if m.get("role") == "user"), "")

    if len(content) < 3:
        messages.append({"role": "assistant", "content": "Bitte gib mir kurz Bescheid, wie ich helfen kann."})
        return {"messages": messages, "is_valid": False, "awaiting_user_input": True}

    return {"is_valid": True, "awaiting_user_input": False}


async def route_node(state: HenkGraphState) -> HenkGraphState:
    if state.get("awaiting_user_input"):
        return {"next_step": None}

    current_agent = state.get("current_agent") or "operator"
    return {
        "current_agent": current_agent,
        "next_step": HandoffAction(kind="agent", name=current_agent).model_dump(),
        "session_state": _session_state(state),
    }


def _validate_handoff(target: str, payload: dict) -> tuple[bool, Optional[str]]:
    if target == "design_henk":
        ok, err = HandoffValidator.validate_henk1_to_design(Henk1ToDesignHenkPayload(**payload))
        return ok, err
    if target == "laserhenk":
        ok, err = HandoffValidator.validate_design_to_laser(DesignHenkToLaserHenkPayload(**payload))
        return ok, err
    if target == "hitl":
        ok, err = HandoffValidator.validate_laser_to_hitl(LaserHenkToHITLPayload(**payload))
        return ok, err
    return False, "Unbekanntes Handoff-Ziel"


async def run_step_node(state: HenkGraphState) -> HenkGraphState:
    next_step_data = state.get("next_step")
    if not next_step_data:
        return {"awaiting_user_input": True}

    action = HandoffAction.model_validate(next_step_data)

    if action.kind == "tool":
        tool = TOOL_REGISTRY.get(action.name)
        if not tool:
            return {"awaiting_user_input": True, "next_step": None}

        result: ToolResult = await tool(action.params, state)
        messages = list(state.get("messages", []))
        messages.append({"role": "assistant", "content": result.text, "metadata": result.metadata})

        state_updates: Dict[str, Any] = {
            "messages": messages,
            "awaiting_user_input": not action.should_continue,
            "next_step": None,
        }

        if action.return_to_agent:
            state_updates["next_step"] = HandoffAction(
                kind="agent",
                name=action.return_to_agent,
                should_continue=action.should_continue,
            ).model_dump()

        state_updates["user_input"] = None  # type: ignore[typeddict-item]
        return state_updates

    agent_factory = AGENT_REGISTRY.get(action.name)
    if not agent_factory:
        return {"awaiting_user_input": True, "next_step": None}

    agent = agent_factory()
    session_state = _session_state(state)

    decision = await agent.process(session_state)
    session_state.current_agent = agent.agent_name

    messages = list(state.get("messages", []))
    if decision.message:
        messages.append({"role": "assistant", "content": decision.message, "sender": agent.agent_name})

    updates: Dict[str, Any] = {
        "messages": messages,
        "session_state": session_state,
        "current_agent": agent.agent_name,
        "awaiting_user_input": not decision.should_continue,
    }

    if decision.action == "handoff":
        payload = decision.action_params or {}
        target = payload.get("target_agent")
        handoff_payload = payload.get("payload") or {}
        ok, err = _validate_handoff(target, handoff_payload)
        if ok:
            session_state_handoffs = getattr(session_state, "handoffs", {}) or {}
            session_state_handoffs[target] = handoff_payload
            session_state.handoffs = session_state_handoffs  # type: ignore[attr-defined]
            updates["session_state"] = session_state
            updates["next_step"] = HandoffAction(
                kind="agent",
                name=target,
                should_continue=True,
            ).model_dump()
            updates["awaiting_user_input"] = False
        else:
            messages.append({"role": "assistant", "content": f"Handoff fehlgeschlagen: {err}"})
            updates["awaiting_user_input"] = True
            updates["next_step"] = None
        return updates

    if decision.action and decision.action in TOOL_REGISTRY:
        updates["next_step"] = HandoffAction(
            kind="tool",
            name=decision.action,
            params=decision.action_params or {},
            should_continue=decision.should_continue,
            return_to_agent=decision.next_agent or agent.agent_name,
        ).model_dump()
        updates["awaiting_user_input"] = False
        return updates

    if decision.next_agent:
        updates["next_step"] = HandoffAction(
            kind="agent",
            name=decision.next_agent,
            params=decision.action_params or {},
            should_continue=decision.should_continue,
        ).model_dump()
        updates["awaiting_user_input"] = False if decision.should_continue else True
        return updates

    updates["next_step"] = None
    return updates

