"""Kompakte KISS-Workflow-Nodes mit strukturierten Actions."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from agents.design_henk import DesignHenkAgent
from agents.henk1 import Henk1Agent
from agents.laserhenk import LaserHenkAgent
from agents.supervisor_agent import SupervisorAgent, SupervisorDecision
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
}


SUPERVISOR = SupervisorAgent()


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

        fabric_code = fabric_dict.get("fabric_code")
        logging.info(f"[RAG] Fabric {fabric_code}: image_urls={len(image_urls)}, local_paths={len(local_paths)}, final_url={image_url}")

        if not image_url:
            logging.warning(f"[RAG] ⚠️ Fabric {fabric_code} has NO images - skipping from image list")
            continue

        # Extract data with robust fallbacks
        name = fabric_dict.get("name") or "Hochwertiger Stoff"
        color = fabric_dict.get("color") or "Klassisch"
        pattern = fabric_dict.get("pattern") or "Uni"
        composition = fabric_dict.get("composition") or "Hochwertige Wollmischung"
        supplier = fabric_dict.get("supplier") or "Formens"

        # Log extracted data for debugging
        logging.info(f"[RAG] Building fabric_image for {fabric_code}: name={name!r}, color={color!r}, pattern={pattern!r}")

        fabric_images.append(
            {
                "url": image_url,
                "fabric_code": fabric_code,
                "name": name,
                "color": color,
                "pattern": pattern,
                "composition": composition,
                "supplier": supplier,
            }
        )
        if len(fabric_images) >= 2:
            break

    if hasattr(session_state, "shown_fabric_images"):
        session_state.shown_fabric_images.extend(fabric_images)

    # Mark that fabrics have been shown to prevent repeated RAG calls
    if fabric_images:
        session_state.henk1_fabrics_shown = True
        logging.info(f"[RAG] ✅ Set henk1_fabrics_shown = True ({len(fabric_images)} images)")

    state["session_state"] = session_state

    if not recommendations:
        state["session_state"] = session_state
        return ToolResult(
            text="Ich konnte gerade keine Stoffe aus der Datenbank laden. Nenne mir kurz deine Lieblingsfarben oder ein Muster, dann versuche ich es erneut.",
            metadata={},
        )

    formatted = "**Passende Stoffe für dich:**\n\n" + "".join(
        (
            f"{idx}. {getattr(rec.fabric, 'name', None) or 'Hochwertiger Stoff'} "
            f"(Code: {getattr(rec.fabric, 'fabric_code', None)}) - "
            f"Farbe: {getattr(rec.fabric, 'color', None) or 'Klassisch'}, "
            f"Muster: {getattr(rec.fabric, 'pattern', None) or 'Uni'}, "
            f"Material: {getattr(rec.fabric, 'composition', None) or 'Edle Wollmischung'}\n"
        )
        for idx, rec in enumerate(recommendations[:5], 1)
    )

    metadata: Dict[str, Any] = {"fabric_images": fabric_images} if fabric_images else {}
    return ToolResult(text=formatted, metadata=metadata)


async def _dalle_tool(params: dict, state: HenkGraphState) -> ToolResult:
    from models.fabric import SelectedFabricData

    session_state = _session_state(state)

    # Extract structured fabric data
    fabric_data_raw = params.get("fabric_data", {})
    if isinstance(fabric_data_raw, dict):
        fabric_data = SelectedFabricData(**fabric_data_raw)
    elif isinstance(fabric_data_raw, SelectedFabricData):
        fabric_data = fabric_data_raw
    else:
        fabric_data = SelectedFabricData()

    # Extract design preferences and style keywords
    design_prefs = params.get("design_preferences", {})
    style_keywords = params.get("style_keywords", [])
    prompt_type = params.get("prompt_type", "outfit_visualization")

    # Build DALL-E prompt with actual fabric data
    if prompt_type == "outfit_visualization":
        prompt = _build_outfit_prompt(fabric_data, design_prefs, style_keywords)
    else:
        prompt = params.get("prompt") or "Mood Board für ein elegantes Outfit"

    # Log for debugging
    logging.info(f"[DALLE Tool] Using fabric_data: {fabric_data.model_dump(exclude_none=True)}")
    logging.info(f"[DALLE Tool] Generated prompt preview: {prompt[:200]}...")

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


def _build_outfit_prompt(fabric_data: "SelectedFabricData", design_prefs: dict, style_keywords: list[str]) -> str:
    """
    Build DALL-E prompt for outfit visualization using structured fabric data.

    Args:
        fabric_data: SelectedFabricData with color, pattern, composition
        design_prefs: Design preferences (revers_type, shoulder_padding, etc.)
        style_keywords: Style keywords

    Returns:
        Detailed DALL-E prompt
    """
    # Extract fabric properties
    color = fabric_data.color or "klassisches Blau"
    pattern = fabric_data.pattern or "Uni"
    composition = fabric_data.composition or "hochwertige Wolle"
    texture = fabric_data.texture or ""

    # Build fabric description
    fabric_desc = f"{color}"
    if pattern and pattern.lower() != "plain" and pattern.lower() != "uni":
        fabric_desc += f" mit {pattern}"
    if texture:
        fabric_desc += f" und {texture}"

    # Extract design details
    revers = design_prefs.get("revers_type", "klassisches Revers")
    shoulder = design_prefs.get("shoulder_padding", "mittlere Schulterpolsterung")
    waistband = design_prefs.get("waistband_type", "klassische Bundfalte")

    # Build style description
    style = ", ".join(style_keywords) if style_keywords else "elegant, maßgeschneidert"

    # Create prompt
    prompt = f"""Create a high-quality fashion editorial photo of a bespoke men's suit in an elegant professional setting.

FABRIC SPECIFICATION:
- Color: {color}
- Pattern: {pattern}
- Material: {composition}
- Texture: {texture or 'glatte, edle Struktur'}

The suit should be made from this exact fabric: {fabric_desc}.

SUIT DESIGN:
- Lapel style: {revers}
- Shoulder: {shoulder}
- Trouser waistband: {waistband}

STYLE: {style}, sophisticated, high-quality menswear photography.

COMPOSITION: Professional fashion photography, clean background, natural lighting, focus on fabric detail and suit construction quality.

NOTE: Accurately represent the fabric color ({color}) and pattern ({pattern}) in the visualization."""

    return prompt


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

    user_message = _latest_content(state.get("messages", []), "user") or state.get("user_input", "")

    decision: SupervisorDecision = await SUPERVISOR.decide_next_step(
        user_message=user_message,
        state=session_state,
        conversation_history=session_state.conversation_history,
    )

    metadata = dict(state.get("metadata", {}))
    metadata.update(
        {
            "supervisor_reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "next_destination": decision.next_destination,
        }
    )

    if decision.next_destination in TOOL_REGISTRY:
        return {
            "session_state": session_state,
            "current_agent": session_state.current_agent or "supervisor",
            "next_step": HandoffAction(
                kind="tool",
                name=decision.next_destination,
                params=decision.action_params or {},
                should_continue=False,
                return_to_agent=session_state.current_agent,
                reasoning=decision.reasoning,
                confidence=decision.confidence,
            ).model_dump(),
            "metadata": metadata,
            "awaiting_user_input": False,
        }

    if decision.next_destination == "clarification":
        messages = list(state.get("messages", []))
        if decision.user_message:
            messages.append(
                {
                    "role": "assistant",
                    "content": decision.user_message,
                    "sender": "supervisor",
                    "metadata": {"reasoning": decision.reasoning, "confidence": decision.confidence},
                }
            )
        return {
            "messages": messages,
            "session_state": session_state,
            "current_agent": "supervisor",
            "awaiting_user_input": True,
            "next_step": None,
            "metadata": metadata,
        }

    if decision.next_destination == "end":
        return {
            "session_state": session_state,
            "current_agent": "supervisor",
            "awaiting_user_input": True,
            "next_step": None,
            "metadata": metadata,
        }

    session_state.current_agent = decision.next_destination

    return {
        "current_agent": decision.next_destination,
        "next_step": HandoffAction(kind="agent", name=decision.next_destination).model_dump(),
        "session_state": session_state,
        "metadata": metadata,
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
    logging.info(f"[RunStep] action_data: {action_data}")
    if not action_data:
        logging.warning("[RunStep] No action_data, returning awaiting_user_input=True")
        return {"awaiting_user_input": True, "next_step": None}

    action = HandoffAction.model_validate(action_data)
    logging.info(f"[RunStep] Executing {action.kind}: {action.name}")

    if action.kind == "tool":
        logging.info(f"[RunStep] Running tool: {action.name} with params: {action.params}")
        return await _run_tool_action(action, state)

    agent_factory = AGENT_REGISTRY.get(action.name)
    if not agent_factory:
        logging.warning(f"[RunStep] Agent {action.name} not found in registry")
        return {"awaiting_user_input": True, "next_step": None}

    logging.info(f"[RunStep] Running agent: {action.name}")
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

    logging.info(f"[AgentStep] {agent.agent_name} decision: action={decision.action}, next_agent={decision.next_agent}, should_continue={decision.should_continue}")

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
        logging.info(f"[AgentStep] Handoff to {target}: ok={ok}")
        return updates

    if decision.action and decision.action in TOOL_REGISTRY:
        logging.info(f"[AgentStep] Tool action detected: {decision.action}, creating next_step for tool execution")
        updates["next_step"] = HandoffAction(
            kind="tool",
            name=decision.action,
            params=decision.action_params or {},
            should_continue=decision.should_continue,
            return_to_agent=decision.next_agent or agent.agent_name,
        ).model_dump()
        updates["awaiting_user_input"] = False
        logging.info(f"[AgentStep] next_step set: {updates['next_step']}")
        return updates

    if decision.next_agent:
        logging.info(f"[AgentStep] Next agent: {decision.next_agent}, should_continue={decision.should_continue}")
        updates["next_step"] = HandoffAction(
            kind="agent",
            name=decision.next_agent,
            params=decision.action_params or {},
            should_continue=decision.should_continue,
        ).model_dump()
        updates["awaiting_user_input"] = False if decision.should_continue else True

    logging.info(f"[AgentStep] Final updates: awaiting_user_input={updates['awaiting_user_input']}, next_step={updates.get('next_step')}")
    return updates

