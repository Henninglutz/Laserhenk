"""Kompakte KISS-Workflow-Nodes mit strukturierten Actions."""

from __future__ import annotations

import logging
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

    # Mark the intent to query RAG immediately to avoid repeated triggers if the DB fails
    session_state.henk1_rag_queried = True
    session_state.rag_context = {"query": query}
    state["session_state"] = session_state

    try:
        recommendations = await RAGTool().search_fabrics(criteria)
    except Exception as exc:  # pragma: no cover - surface the issue instead of hardcoded fallbacks
        logging.error("[RAGTool] Stoffsuche fehlgeschlagen", exc_info=exc)
        raise

    fabrics = [
        getattr(rec, "fabric", None).model_dump()
        if getattr(rec, "fabric", None) and hasattr(rec.fabric, "model_dump")
        else (getattr(rec, "fabric", None) or {})
        for rec in recommendations[:10]
    ]
    session_state.rag_context = {"fabrics": fabrics, "query": query}
    session_state.henk1_rag_queried = True

    fabric_images = []
    for rec in recommendations[:5]:
        fabric = getattr(rec, "fabric", None) or getattr(rec, "to_dict", lambda: {})()
        if not fabric:
            continue
        fabric_dict = fabric.model_dump() if hasattr(fabric, "model_dump") else dict(fabric)
        image_urls = fabric_dict.get("image_urls") or []
        local_paths = fabric_dict.get("local_image_paths") or []
        image_url = (image_urls[0] if image_urls else None) or (local_paths[0] if local_paths else None)
        if not image_url:
            continue
        fabric_images.append(
            {
                "url": image_url,
                "fabric_code": fabric_dict.get("fabric_code"),
                "name": fabric_dict.get("name", "Hochwertiger Stoff"),
                "color": fabric_dict.get("color"),
                "pattern": fabric_dict.get("pattern"),
                "composition": fabric_dict.get("composition"),
            }
        )
        if len(fabric_images) >= 2:
            break

    if hasattr(session_state, "shown_fabric_images"):
        session_state.shown_fabric_images.extend(fabric_images)

    state["session_state"] = session_state

    if not recommendations:
        state["session_state"] = session_state
        return ToolResult(
            text="Ich konnte gerade keine Stoffe aus der Datenbank laden. Nenne mir kurz deine Lieblingsfarben oder ein Muster, dann versuche ich es erneut.",
            metadata={},
        )

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


async def _show_fabric_images(params: dict, state: HenkGraphState) -> ToolResult:
    session_state = _session_state(state)
    rag_context = getattr(session_state, "rag_context", {}) or {}
    fabrics = rag_context.get("fabrics", [])

    if not fabrics:
        return ToolResult(
            text="Ich habe gerade keine Stoffbilder finden können. Nenne mir kurz deine Wunschfarben, dann suche ich erneut.",
            metadata={},
        )

    fabrics_with_images = []
    for fabric in fabrics:
        image_urls = fabric.get("image_urls") or []
        local_paths = fabric.get("local_image_paths") or []
        # Prefer local paths (served via /fabrics/images) to avoid broken external links
        image_url = (local_paths[0] if local_paths else None) or (image_urls[0] if image_urls else None)
        if not image_url:
            continue
        fabrics_with_images.append(
            {
                "url": image_url,
                "fabric_code": fabric.get("fabric_code", ""),
                "name": fabric.get("name", "Hochwertiger Stoff"),
                "color": fabric.get("color", ""),
                "pattern": fabric.get("pattern", ""),
                "composition": fabric.get("composition", ""),
            }
        )
        if len(fabrics_with_images) >= params.get("limit", 2):
            break

    if not fabrics_with_images:
        return ToolResult(
            text="Die Stoffbilder sind noch nicht verfügbar. Ich beschreibe dir gern die Stoffe – welche Farbe interessiert dich am meisten?",
            metadata={},
        )

    message = "🎨 **Hier sind deine Stoff-Empfehlungen mit Bildern!**\n\n"
    for idx, fabric in enumerate(fabrics_with_images, 1):
        message += (
            f"{idx}. {fabric['name']} (Ref: {fabric['fabric_code']})\n"
            f"   Farbe: {fabric['color'] or 'klassisch'} | Muster: {fabric['pattern'] or 'uni'}\n"
        )

    session_state.shown_fabric_images.extend(fabrics_with_images)
    state["session_state"] = session_state
    return ToolResult(text=message, metadata={"fabric_images": fabrics_with_images})


TOOL_REGISTRY: Dict[str, Callable[[dict, HenkGraphState], Any]] = {
    "rag_tool": _rag_tool,
    "dalle_mood_board": _dalle_tool,
    "dalle_tool": _dalle_tool,
    "mark_favorite_fabric": _mark_favorite_fabric,
    "show_fabric_images": _show_fabric_images,
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

    try:
        result: ToolResult = await tool(action.params, state)
    except Exception as exc:  # pragma: no cover
        logging.error("[ToolRunner] Tool failed", exc_info=exc)
        result = ToolResult(text="Da ist etwas schiefgegangen bei der Ausführung. Versuchen wir es gleich nochmal.")
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "assistant",
            "content": result.text,
            "metadata": result.metadata,
            "sender": action.name,
        }
    )
    session_state = _session_state(state)

    next_step = (
        HandoffAction(kind="agent", name=action.return_to_agent, should_continue=action.should_continue).model_dump()
        if action.return_to_agent
        else None
    )

    return {
        "messages": messages,
        "session_state": session_state,
        "awaiting_user_input": not action.should_continue,
        "next_step": next_step,
        "user_input": None,  # type: ignore[typeddict-item]
    }


async def _run_agent_step(agent: Any, action: HandoffAction, state: HenkGraphState) -> HenkGraphState:
    session_state = _session_state(state)
    decision = await agent.process(session_state)
    session_state.current_agent = agent.agent_name

    messages = list(state.get("messages", []))
    if decision.message and agent.agent_name != "operator":
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

