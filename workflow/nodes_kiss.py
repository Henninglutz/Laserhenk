"""Kompakte KISS-Workflow-Nodes mit strukturierten Actions."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from agents.design_henk import DesignHenkAgent
from agents.henk1 import Henk1Agent
from agents.laserhenk import LaserHenkAgent
from agents.operator import OperatorAgent
from models.customer import SessionState
from models.handoff import (
    DesignHenkToLaserHenkPayload,
    HandoffValidator,
    Henk1ToDesignHenkPayload,
    LaserHenkToHITLPayload,
)
from models.tools import DALLEImageRequest
from tools.dalle_tool import DALLETool
from tools.fabric_preferences import build_fabric_search_criteria
from tools.rag_tool import RAGTool
from workflow.graph_state import HenkGraphState


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
    if isinstance(session_state, SessionState):
        return session_state
    parsed = SessionState(**(session_state or {}))
    state["session_state"] = parsed
    return parsed


def _normalize_role(role: Optional[str]) -> str:
    if role in {"human", "user"}:
        return "user"
    if role in {"ai", "assistant"}:
        return "assistant"
    return role or "assistant"


def _serialize_message(msg: Any) -> dict:
    if isinstance(msg, dict):
        msg_role = _normalize_role(msg.get("role"))
        return {"role": msg_role, "content": msg.get("content", ""), **{k: v for k, v in msg.items() if k not in {"role", "content"}}}

    msg_role = _normalize_role(getattr(msg, "type", None) or getattr(msg, "role", None))
    data = {"role": msg_role, "content": getattr(msg, "content", "")}
    metadata = getattr(msg, "metadata", None) or getattr(msg, "additional_kwargs", None)
    if metadata:
        data["metadata"] = metadata
    sender = getattr(msg, "sender", None) or getattr(msg, "name", None)
    if sender:
        data["sender"] = sender
    return data


def _latest_content(messages: list, role: str) -> str:
    normalized_role = _normalize_role(role)
    for msg in reversed(messages):
        parsed = _serialize_message(msg)
        if parsed.get("role") == normalized_role:
            return str(parsed.get("content", "")).strip()
    return ""


async def _rag_tool(params: dict, state: HenkGraphState) -> ToolResult:
    session_state = _session_state(state)

    query = params.get("query") or params.get("prompt") or ""
    if not query:
        return ToolResult(text="Ich brauche noch ein paar Details für die Stoffsuche.")

    criteria, updated_state, _, _ = build_fabric_search_criteria(query, params, session_state)
    session_state = updated_state or session_state

    try:
        recommendations = await RAGTool().search_fabrics(criteria)
    except Exception as exc:  # pragma: no cover - defensive fallback when DB is unavailable
        logging.warning("[RAGTool] Fallback because DB not reachable", exc_info=exc)
        fallback_fabrics = [
            {"fabric_code": "NAVY_WOOL", "name": "Feiner Navy-Wolltwill", "color": "navy", "pattern": "uni"},
            {"fabric_code": "MID_GREY_FLANNEL", "name": "Mittlerer Grau-Flanell", "color": "grau", "pattern": "melange"},
            {"fabric_code": "BEIGE_LINEN", "name": "Leichter Beige-Leinenmix", "color": "beige", "pattern": "uni"},
        ]
        session_state.rag_context = {"fabrics": fallback_fabrics, "query": query, "source": "fallback"}
        session_state.henk1_rag_queried = True
        state["session_state"] = session_state

        formatted = (
            "Unsere Stoffdatenbank ist gerade nicht erreichbar. Hier sind drei beliebte Optionen: "
            "Navy-Wolle, mittlerer Grau-Flanell oder ein beiger Leinen-Mix. Was spricht dich am meisten an?"
        )
        return ToolResult(text=formatted, metadata={})

    fabrics = [
        getattr(rec, "fabric", None).model_dump()
        if getattr(rec, "fabric", None) and hasattr(rec.fabric, "model_dump")
        else (getattr(rec, "fabric", None) or {})
        for rec in recommendations[:10]
    ]
    session_state.rag_context = {"fabrics": fabrics, "query": query}
    session_state.henk1_rag_queried = True

    fabric_images = [
        {
            "url": f"/fabrics/images/{(rec.fabric.fabric_code or 'fabric').replace('/', '_')}.jpg",
            "fabric_code": rec.fabric.fabric_code,
            "name": rec.fabric.name,
            "color": rec.fabric.color,
            "pattern": rec.fabric.pattern,
        }
        for rec in recommendations[:2]
        if getattr(rec, "fabric", None)
    ]

    if hasattr(session_state, "shown_fabric_images"):
        session_state.shown_fabric_images.extend(fabric_images)

    state["session_state"] = session_state

    formatted = "**Passende Stoffe für dich:**\n\n" + "".join(
        f"{idx}. {getattr(rec.fabric, 'name', None) or 'Hochwertiger Stoff'} (Code: {getattr(rec.fabric, 'fabric_code', None)}) - "
        f"Farbe: {getattr(rec.fabric, 'color', None) or 'klassisch'}, Muster: {getattr(rec.fabric, 'pattern', None) or 'uni'}\n"
        for idx, rec in enumerate(recommendations[:5], 1)
    )

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

    if not fabric:
        return ToolResult(text="Ich habe diesen Stoff leider nicht gefunden.")

    session_state.favorite_fabric = fabric
    state["session_state"] = session_state
    return ToolResult(text=f"Alles klar, Stoff {fabric_code} ist jetzt dein Favorit.", metadata={"favorite_fabric": fabric})


TOOL_REGISTRY: Dict[str, Callable[[dict, HenkGraphState], Any]] = {
    "rag_tool": _rag_tool,
    "dalle_mood_board": _dalle_tool,
    "dalle_tool": _dalle_tool,
    "mark_favorite_fabric": _mark_favorite_fabric,
}


async def validate_node(state: HenkGraphState) -> HenkGraphState:
    messages = list(state.get("messages", []))
    content = _latest_content(messages, "user")

    if len(content) < 3:
        messages.append({"role": "assistant", "content": "Bitte gib mir kurz Bescheid, wie ich helfen kann."})
        return {"messages": messages, "is_valid": False, "awaiting_user_input": True}

    return {"is_valid": True, "awaiting_user_input": False}


async def route_node(state: HenkGraphState) -> HenkGraphState:
    session_state = _session_state(state)
    session_state.conversation_history = [_serialize_message(m) for m in state.get("messages", [])]

    if state.get("awaiting_user_input"):
        return {"next_step": None, "session_state": session_state}

    current_agent = state.get("current_agent") or "operator"
    return {
        "current_agent": current_agent,
        "next_step": HandoffAction(kind="agent", name=current_agent).model_dump(),
        "session_state": session_state,
    }


def _validate_handoff(target: str, payload: dict) -> tuple[bool, Optional[str]]:
    mapping = {
        "design_henk": (Henk1ToDesignHenkPayload, HandoffValidator.validate_henk1_to_design),
        "laserhenk": (DesignHenkToLaserHenkPayload, HandoffValidator.validate_design_to_laser),
        "hitl": (LaserHenkToHITLPayload, HandoffValidator.validate_laser_to_hitl),
    }

    model_cls, validator = mapping.get(target, (None, None))
    if not model_cls or not validator:
        return False, "Unbekanntes Handoff-Ziel"

    ok, err = validator(model_cls(**payload))
    return ok, err


async def run_step_node(state: HenkGraphState) -> HenkGraphState:
    action_data = state.get("next_step")
    if not action_data:
        return {"awaiting_user_input": True, "next_step": None}

    action = HandoffAction.model_validate(action_data)

    if action.kind == "tool":
        return await _run_tool_action(action, state)

    agent_factory = AGENT_REGISTRY.get(action.name)
    if not agent_factory:
        return {"awaiting_user_input": True, "next_step": None}

    return await _run_agent_step(agent_factory(), action, state)


async def _run_tool_action(action: HandoffAction, state: HenkGraphState) -> HenkGraphState:
    tool = TOOL_REGISTRY.get(action.name)
    if not tool:
        return {"awaiting_user_input": True, "next_step": None}

    result: ToolResult = await tool(action.params, state)
    messages = list(state.get("messages", []))
    messages.append({"role": "assistant", "content": result.text, "metadata": result.metadata})

    next_step = (
        HandoffAction(kind="agent", name=action.return_to_agent, should_continue=action.should_continue).model_dump()
        if action.return_to_agent
        else None
    )

    return {
        "messages": messages,
        "awaiting_user_input": not action.should_continue,
        "next_step": next_step,
        "user_input": None,  # type: ignore[typeddict-item]
    }


async def _run_agent_step(agent: Any, action: HandoffAction, state: HenkGraphState) -> HenkGraphState:
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
        "next_step": None,
    }

    if decision.action == "handoff":
        payload = decision.action_params or {}
        target = payload.get("target_agent")
        handoff_payload = payload.get("payload") or {}
        ok, err = _validate_handoff(target, handoff_payload)
        if ok:
            session_state.handoffs[target] = handoff_payload  # type: ignore[index]
            updates["next_step"] = HandoffAction(kind="agent", name=target, should_continue=True).model_dump()
            updates["awaiting_user_input"] = False
        else:
            messages.append({"role": "assistant", "content": f"Handoff fehlgeschlagen: {err}"})
            updates["awaiting_user_input"] = True
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

