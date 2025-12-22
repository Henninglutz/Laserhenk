"""Kompakte KISS-Workflow-Nodes mit strukturierten Actions."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from agents.design_henk import DesignHenkAgent
from agents.henk1 import Henk1Agent
from agents.laserhenk import LaserHenkAgent
from agents.supervisor_agent import SupervisorAgent, SupervisorDecision
from backend.services.image_policy import ImagePolicyAgent
from models.customer import SessionState
from models.handoff import (
    DesignHenkToLaserHenkPayload,
    HandoffValidator,
    Henk1ToDesignHenkPayload,
    LaserHenkToHITLPayload,
)
from models.api_payload import ImagePolicyDecision
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


def _parse_appointment_date(message: str) -> Optional[str]:
    if not message:
        return None

    lowered = message.lower()
    today = date.today()

    if "übermorgen" in lowered:
        return (today + timedelta(days=2)).isoformat()
    if "morgen" in lowered:
        return (today + timedelta(days=1)).isoformat()

    match_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", message)
    if match_iso:
        return f"{match_iso.group(1)}-{match_iso.group(2)}-{match_iso.group(3)}"

    match_dmy = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", message)
    if match_dmy:
        day, month, year = match_dmy.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    match_dm = re.search(r"\b(\d{1,2})\.(\d{1,2})\b", message)
    if match_dm:
        day, month = match_dm.groups()
        return f"{today.year}-{int(month):02d}-{int(day):02d}"

    return None


def _parse_appointment_time(message: str) -> Optional[str]:
    if not message:
        return None

    match_time = re.search(r"\b([01]?\d|2[0-3])[:.](\d{2})\b", message)
    if match_time:
        hour, minute = match_time.groups()
        return f"{int(hour):02d}:{minute}"

    match_hour = re.search(r"\bum\s*([01]?\d|2[0-3])\s*uhr\b", message.lower())
    if match_hour:
        hour = match_hour.group(1)
        return f"{int(hour):02d}:00"

    return None


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
        weight = fabric_dict.get("weight_g_m2")  # Grammatur

        # Log extracted data for debugging
        logging.info(f"[RAG] Building fabric_image for {fabric_code}: name={name!r}, color={color!r}, pattern={pattern!r}, weight={weight}")

        fabric_images.append(
            {
                "url": image_url,
                "fabric_code": fabric_code,
                "name": name,
                "color": color,
                "pattern": pattern,
                "composition": composition,
                "supplier": supplier,
                "weight_g_m2": weight,
            }
        )
        if len(fabric_images) >= 5:  # Show 5 fabrics
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
            f"{idx}. **{getattr(rec.fabric, 'name', None) or 'Hochwertiger Stoff'}** "
            f"(Ref: {getattr(rec.fabric, 'fabric_code', None)})\n"
            f"   • Farbe: {getattr(rec.fabric, 'color', None) or 'Klassisch'}\n"
            f"   • Muster: {getattr(rec.fabric, 'pattern', None) or 'Uni'}\n"
            f"   • Material: {getattr(rec.fabric, 'composition', None) or 'Edle Wollmischung'}\n"
            f"   • Grammatur: {getattr(rec.fabric, 'weight_g_m2', None) or 'N/A'} g/m²\n\n"
        )
        for idx, rec in enumerate(recommendations[:5], 1)
    )

    metadata: Dict[str, Any] = {"fabric_images": fabric_images} if fabric_images else {}
    return ToolResult(text=formatted, metadata=metadata)


async def _dalle_tool(params: dict, state: HenkGraphState) -> ToolResult:
    from models.fabric import SelectedFabricData

    session_state = _session_state(state)
    image_policy_raw = state.get("image_policy")
    image_policy = (
        ImagePolicyDecision(**image_policy_raw)
        if isinstance(image_policy_raw, dict)
        else image_policy_raw
    )

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
    session_id = params.get("session_id", session_state.session_id)

    # Add vest preference from session state to design_prefs
    if hasattr(session_state, 'wants_vest') and session_state.wants_vest is not None:
        design_prefs["wants_vest"] = session_state.wants_vest
        logging.info(f"[DALLE Tool] Added wants_vest={session_state.wants_vest} to design_prefs")
    else:
        logging.info(f"[DALLE Tool] wants_vest not set: hasattr={hasattr(session_state, 'wants_vest')}, value={getattr(session_state, 'wants_vest', None)}")

    # Log for debugging
    logging.info(f"[DALLE Tool] Using fabric_data: {fabric_data.model_dump(exclude_none=True)}")
    logging.info(f"[DALLE Tool] Final design_prefs: {design_prefs}")

    # OPTION 1: Use fabric image for composite (if available)
    if fabric_data.image_url and prompt_type == "outfit_visualization":
        logging.info(f"[DALLE Tool] Using composite generation with fabric image: {fabric_data.image_url}")

        # Convert SelectedFabricData to fabric dict format expected by generate_mood_board_with_fabrics
        fabric_dict = {
            "fabric_code": fabric_data.fabric_code or "SELECTED",
            "name": f"{fabric_data.color or 'Eleganter'} {fabric_data.pattern or 'Stoff'}",
            "color": fabric_data.color or "klassisch",
            "pattern": fabric_data.pattern or "Uni",
            "composition": fabric_data.composition or "hochwertige Wolle",
            "supplier": fabric_data.supplier or "Formens",
            "image_urls": [fabric_data.image_url],  # Expected format: list of URLs
        }

        # Determine occasion from style keywords or default
        occasion = "Business"  # Default
        if style_keywords:
            if any(kw in ["Hochzeit", "wedding", "festlich"] for kw in style_keywords):
                occasion = "Hochzeit"
            elif any(kw in ["Gala", "Abend", "evening"] for kw in style_keywords):
                occasion = "Gala"
            elif any(kw in ["casual", "leger", "freizeit"] for kw in style_keywords):
                occasion = "Casual"

        # Generate composite mood board with actual fabric thumbnail and design details
        response = await DALLETool().generate_mood_board_with_fabrics(
            fabrics=[fabric_dict],
            occasion=occasion,
            style_keywords=style_keywords,
            design_preferences=design_prefs,
            session_id=session_id,
            decision=image_policy,
        )

    # OPTION 2: Text-only prompt (fallback if no fabric image)
    else:
        if not fabric_data.image_url:
            logging.info("[DALLE Tool] No fabric image URL available, using text-only prompt")

        # Build DALL-E prompt with actual fabric data
        if prompt_type == "outfit_visualization":
            prompt = _build_outfit_prompt(fabric_data, design_prefs, style_keywords)
        else:
            prompt = params.get("prompt") or "Mood Board für ein elegantes Outfit"

        logging.info(f"[DALLE Tool] Generated prompt preview: {prompt[:200]}...")

        request = params.get("request")
        request = request if isinstance(request, DALLEImageRequest) else DALLEImageRequest(prompt=prompt)

        response = await DALLETool().generate_image(request=request, decision=image_policy)

    # Store generated image in session state
    image_url = getattr(response, "image_url", None)
    if image_url:
        session_state.mood_image_url = image_url
        session_state.image_generation_history.append({"image_url": image_url, "type": "dalle_composite" if fabric_data.image_url else "dalle"})
        state["session_state"] = session_state

    text = response.error if getattr(response, "error", None) else "Hier ist dein illustratives Mood Board. Die echten Stoffbilder findest du separat."
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
    wants_vest = design_prefs.get("wants_vest")
    notes_normalized = (design_prefs.get("notes_normalized") or "").lower()

    trouser_color = None
    trouser_color_map = {
        "dunkelblau": "navy blue",
        "navy": "navy blue",
        "marine": "navy blue",
        "blau": "blue",
        "blue": "blue",
        "schwarz": "black",
        "black": "black",
        "grau": "grey",
        "grey": "grey",
        "beige": "beige",
        "braun": "brown",
    }
    for key, color in trouser_color_map.items():
        if key in notes_normalized:
            trouser_color = color
            break

    # Build vest instruction
    vest_instruction = ""
    if wants_vest is False:
        vest_instruction = "\n- Configuration: TWO-PIECE suit (jacket and trousers ONLY, NO vest/waistcoat/gilet)"
    elif wants_vest is True:
        vest_instruction = "\n- Configuration: THREE-PIECE suit (jacket, vest, and trousers)"

    trouser_color_instruction = (
        f"\n- Trouser color: {trouser_color} (contrast trousers; jacket stays in fabric tone)"
        if trouser_color
        else ""
    )

    # Build style description
    style = ", ".join(style_keywords) if style_keywords else "elegant, maßgeschneidert"

    # Create prompt
    prompt = f"""Create a high-quality fashion editorial photo of a bespoke men's suit in an elegant professional setting.

FABRIC SPECIFICATION:
- Color: {color}
- Pattern: {pattern}
- Material: {composition}
- Texture: {texture or 'glatte, edle Struktur'}

Use the fabric description only as inspiration; do NOT claim or replicate any specific real fabric pattern.

SUIT DESIGN:
- Lapel style: {revers}
- Shoulder: {shoulder}
- Trouser waistband: {waistband}{trouser_color_instruction}{vest_instruction}

STYLE: {style}, sophisticated, high-quality menswear photography.

COMPOSITION: Professional fashion photography, clean background, natural lighting, focus on garment construction quality.

IMPORTANT: Realistic photograph only - NOT illustration, NOT drawing, NOT sketch. High-quality professional photography with photorealistic details and natural lighting. Absolutely exclude any vest if not requested.

NOTE: Use the fabric color ({color}) and pattern ({pattern}) as general inspiration only; avoid exact replication."""

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


async def _crm_create_lead(params: dict, state: HenkGraphState) -> ToolResult:
    """Create CRM lead in Pipedrive."""
    from tools.crm_tool import CRMTool
    from models.tools import CRMLeadCreate

    session_state = _session_state(state)

    # Extract customer data
    customer_name = params.get("customer_name") or session_state.customer.name or "Interessent"
    customer_email = params.get("customer_email") or session_state.customer.email
    customer_phone = params.get("customer_phone") or session_state.customer.phone

    # CRITICAL: Validate Email BEFORE creating lead
    # Email is required for CRM person creation in Pipedrive
    if not customer_email:
        logging.error(f"[CRM] Lead creation failed: No email provided for {customer_name}")

        # Create MOCK lead to prevent infinite loop
        session_id = params.get("session_id", "unknown")
        mock_lead_id = f"NO_EMAIL_{session_id[:8]}"
        session_state.customer.crm_lead_id = mock_lead_id
        state["session_state"] = session_state

        return ToolResult(
            text="⚠️ Email-Adresse erforderlich für Kontaktsicherung.\n\n"
                 "Bitte geben Sie Ihre Email-Adresse an, damit wir Sie erreichen können.",
            metadata={
                "error": "missing_email",
                "crm_lead_id": mock_lead_id,
                "mock": True,
                "validation_failed": True,
            },
        )

    # Prepare lead data
    lead_data = CRMLeadCreate(
        customer_name=customer_name,
        email=customer_email,
        phone=customer_phone,
        notes=f"Mood board: {params.get('mood_image_url', 'N/A')}",
        deal_value=2000.0,  # Default suit value, can be adjusted
    )

    # Create lead
    crm_tool = CRMTool()
    response = await crm_tool.create_lead(lead_data)

    if response.success:
        # Store CRM lead ID in session state
        session_state.customer.crm_lead_id = response.lead_id
        state["session_state"] = session_state

        return ToolResult(
            text=f"✅ Lead erfolgreich im CRM gesichert (ID: {response.lead_id})",
            metadata={"crm_lead_id": response.lead_id, "deal_id": response.deal_id},
        )
    else:
        # CRITICAL FIX: Create MOCK lead to prevent infinite loop when Pipedrive is not configured
        logging.warning(f"[CRM] Lead creation failed: {response.message} - Creating MOCK lead to prevent infinite loop")
        session_id = params.get("session_id", "unknown")
        mock_lead_id = f"MOCK_CRM_{session_id[:8]}"
        session_state.customer.crm_lead_id = mock_lead_id
        state["session_state"] = session_state

        return ToolResult(
            text=f"✅ Lead gesichert (Dev-Modus: {mock_lead_id})\n\n"
                 f"💡 Hinweis: Pipedrive CRM ist nicht konfiguriert. "
                 f"Bitte PIPEDRIVE_API_KEY in .env setzen für echte Lead-Erstellung.",
            metadata={"crm_lead_id": mock_lead_id, "mock": True, "error": response.message},
        )


async def _crm_create_appointment(params: dict, state: HenkGraphState) -> ToolResult:
    """Create appointment in Pipedrive."""
    from tools.crm_tool import CRMTool
    from models.tools import CRMAppointmentCreate

    session_state = _session_state(state)

    # Ensure CRM lead exists
    if not session_state.customer.crm_lead_id:
        return ToolResult(
            text="Fehler: CRM Lead muss zuerst erstellt werden",
            metadata={},
        )

    # Extract appointment data
    appointment_data = CRMAppointmentCreate(
        person_id=session_state.customer.crm_lead_id,
        subject=params.get("subject", "Maßerfassung für maßgeschneiderten Anzug"),
        due_date=params.get("due_date"),
        due_time=params.get("due_time", "14:00"),
        duration=params.get("duration", "01:30"),
        location=params.get("location"),
        note=params.get("note", f"Kunde: {session_state.customer.name}"),
        deal_id=params.get("deal_id"),
    )

    # Create appointment
    crm_tool = CRMTool()
    response = await crm_tool.create_appointment(appointment_data)

    if response.success:
        return ToolResult(
            text=f"✅ Termin erfolgreich erstellt (ID: {response.appointment_id})",
            metadata={"appointment_id": response.appointment_id},
        )
    else:
        logging.error(f"[CRM] Appointment creation failed: {response.message}")
        return ToolResult(
            text=f"⚠️ Termin konnte nicht erstellt werden: {response.message}",
            metadata={},
        )


TOOL_REGISTRY: Dict[str, Callable[[dict, HenkGraphState], Any]] = {
    "rag_tool": _rag_tool,
    "dalle_mood_board": _dalle_tool,
    "dalle_tool": _dalle_tool,
    "mark_favorite_fabric": _mark_favorite_fabric,
    "show_fabric_images": _show_fabric_images,
    "crm_create_lead": _crm_create_lead,
    "crm_create_appointment": _crm_create_appointment,
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

    # EMAIL DETECTION (highest priority - needed for CRM lead creation)
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, user_message)
    if email_match and not session_state.customer.email:
        email = email_match.group(0)
        session_state.customer.email = email
        state["session_state"] = session_state
        logger.info(f"[RouteNode] Email detected and stored: {email}")

        # If we're in design_henk waiting for email, route back to design_henk
        if session_state.current_agent == "design_henk":
            return {
                "current_agent": "design_henk",
                "next_step": HandoffAction(kind="agent", name="design_henk", should_continue=True).model_dump(),
                "session_state": session_state,
                "metadata": {"email_captured": email},
            }

    # FABRIC FEEDBACK DETECTION
    # Check if we're in HENK1 phase and fabrics were shown but no favorite selected yet
    if (
        session_state.current_agent == "henk1"
        and session_state.henk1_fabrics_shown
        and not session_state.favorite_fabric
        and len(session_state.shown_fabric_images) > 0
    ):
        user_message_lower = user_message.lower().strip()

        # Check for fabric feedback keywords (color/pattern changes)
        fabric_feedback_keywords = [
            "zu hell", "zu dunkel", "heller", "dunkler", "andere farbe",
            "anderes muster", "einfarbig", "gemustert", "uni", "kariert",
            "gestreift", "anders", "nicht passend", "andere stoffe",
        ]

        if any(keyword in user_message_lower for keyword in fabric_feedback_keywords):
            logger.info(f"[RouteNode] Fabric feedback detected: {user_message}")
            # Reset fabric shown flag to allow new RAG search
            session_state.henk1_fabrics_shown = False
            state["session_state"] = session_state

            # Route back to HENK1 with RAG tool action
            return {
                "current_agent": "henk1",
                "next_step": HandoffAction(
                    kind="tool",
                    name="rag_tool",
                    params={"query": user_message, "colors": [], "patterns": []},
                    should_continue=True,
                    return_to_agent="henk1",
                ).model_dump(),
                "session_state": session_state,
                "metadata": {"fabric_feedback": user_message},
            }

    # MOOD BOARD APPROVAL DETECTION
    # Check if we're in Design HENK phase waiting for mood board approval
    if (
        session_state.current_agent == "design_henk"
        and session_state.mood_image_url
        and not session_state.image_state.mood_board_approved
    ):
        user_message_lower = user_message.lower().strip()

        # Check for approval keywords
        approval_keywords = [
            "ja", "yes", "genehmigt", "approved", "perfekt", "perfect",
            "super", "toll", "gefällt mir", "passt", "ok", "okay",
            "bestätigt", "confirmed", "genau so", "stimmt",
        ]

        if any(keyword in user_message_lower for keyword in approval_keywords):
            # User approved the mood board
            logger.info("[RouteNode] Mood board approved by user")
            session_state.image_state.mood_board_approved = True
            state["session_state"] = session_state

            # Route back to Design HENK to continue with CRM lead creation
            return {
                "current_agent": "design_henk",
                "next_step": HandoffAction(kind="agent", name="design_henk", should_continue=True).model_dump(),
                "session_state": session_state,
                "metadata": {"mood_board_approved": True},
            }

        # Check for rejection/feedback keywords
        feedback_keywords = [
            "nein", "no", "nicht", "anders", "ändern", "anpassen",
            "change", "modify", "andere", "lieber", "stattdessen",
        ]

        if any(keyword in user_message_lower for keyword in feedback_keywords) or len(user_message) > 20:
            # User wants changes - store feedback
            logger.info(f"[RouteNode] Mood board feedback from user: {user_message}")
            session_state.image_state.mood_board_feedback = user_message
            state["session_state"] = session_state

            # Route back to Design HENK to regenerate
            return {
                "current_agent": "design_henk",
                "next_step": HandoffAction(kind="agent", name="design_henk", should_continue=True).model_dump(),
                "session_state": session_state,
                "metadata": {"mood_board_feedback": user_message},
            }

    # APPOINTMENT LOCATION + DATE/TIME DETECTION
    if (
        session_state.customer.crm_lead_id
        and not session_state.customer.crm_lead_id.startswith("HENK1_LEAD")
    ):
        prefs = session_state.customer.appointment_preferences or {}
        user_message_lower = user_message.lower().strip()

        location = prefs.get("location")
        if not location:
            if any(word in user_message_lower for word in ["zu hause", "zuhause", "daheim", "bei mir", "home", "bei mir zu hause"]):
                location = "Kunde zu Hause"
            elif any(word in user_message_lower for word in ["büro", "office", "arbeit", "firma", "im büro", "ins büro"]):
                location = "Im Büro"

        due_date = prefs.get("due_date") or _parse_appointment_date(user_message)
        due_time = prefs.get("due_time") or _parse_appointment_time(user_message)

        if location or due_date or due_time:
            logger.info(
                "[RouteNode] Appointment info detected: location=%s, date=%s, time=%s",
                location,
                due_date,
                due_time,
            )

            session_state.customer.appointment_preferences = {
                "location": location,
                "due_date": due_date,
                "due_time": due_time,
                "notes": "Henning bringt Stoffmuster mit zur Maßerfassung",
            }
            state["session_state"] = session_state

        missing = []
        if not location:
            missing.append("Ort (bei Ihnen zu Hause oder im Büro)")
        if not due_date:
            missing.append("Datum (z. B. 12.02. oder 2025-02-12)")
        if not due_time:
            missing.append("Uhrzeit (z. B. 14:30 oder um 14 Uhr)")

        if missing:
            prompt = "Für die Terminplanung brauche ich noch:\n\n" + "\n".join(
                f"• {item}" for item in missing
            )
            messages = list(state.get("messages", []))
            messages.append({"role": "assistant", "content": prompt, "sender": "design_henk"})

            return {
                "messages": messages,
                "session_state": session_state,
                "awaiting_user_input": True,
                "next_step": None,
                "metadata": {"appointment_pending": True},
            }

        if location and due_date and due_time and not prefs.get("appointment_created"):
            session_state.customer.appointment_preferences["appointment_created"] = True
            state["session_state"] = session_state

            return {
                "session_state": session_state,
                "current_agent": session_state.current_agent or "design_henk",
                "next_step": HandoffAction(
                    kind="tool",
                    name="crm_create_appointment",
                    params={
                        "subject": "Maßerfassung für maßgeschneiderten Anzug",
                        "due_date": due_date,
                        "due_time": due_time,
                        "duration": "01:00",
                        "location": location,
                        "note": "Maßerfassung mit Henning. Bitte Stoffmuster mitbringen.",
                    },
                    should_continue=True,
                    return_to_agent=session_state.current_agent,
                ).model_dump(),
                "awaiting_user_input": False,
                "metadata": {"appointment_requested": True},
            }

        if location and due_date and due_time:
            # Generate summary message
            fabric_info = session_state.favorite_fabric or {}
            fabric_name = fabric_info.get("name", "Ausgewählter Stoff")
            fabric_code = fabric_info.get("fabric_code", "N/A")
            fabric_color = fabric_info.get("color", "")
            fabric_pattern = fabric_info.get("pattern", "")
            fabric_composition = fabric_info.get("composition", "")

            # Extract customer info
            customer_name = session_state.customer.name or "Interessent"
            customer_email = session_state.customer.email or "Noch nicht angegeben"
            customer_phone = session_state.customer.phone or "Noch nicht angegeben"

            # CRM Lead info
            crm_lead_id = session_state.customer.crm_lead_id or "N/A"
            is_mock = crm_lead_id.startswith("MOCK_CRM")

            # Vest preference
            vest_text = "Zweiteiler (ohne Weste)" if session_state.wants_vest is False else "Dreiteiler (mit Weste)" if session_state.wants_vest is True else "Zweiteiler"

            summary_message = f"""✅ **Perfekt! Hier ist Ihre Zusammenfassung:**

📋 **Ihr maßgeschneiderter Anzug**
━━━━━━━━━━━━━━━━━━━━━━

**Stoff:**
• {fabric_name} (Ref: {fabric_code})
• Farbe: {fabric_color}
• Muster: {fabric_pattern}
• Material: {fabric_composition}

**Design:**
• Revers: {session_state.design_preferences.revers_type or 'Spitzrevers'}
• Schulter: {session_state.design_preferences.shoulder_padding or 'mittel'} Polsterung
• Hosenbund: {session_state.design_preferences.waistband_type or 'Bundfalte'}
• Konfiguration: {vest_text}

**Anlass:** {getattr(session_state.henk1_to_design_payload, 'occasion', None) or 'Business'}

👤 **Kundendaten für Henning:**
• Name: {customer_name}
• E-Mail: {customer_email}
• Telefon: {customer_phone}
• CRM Lead: {crm_lead_id}{'  (Dev-Modus)' if is_mock else ''}

📍 **Nächster Schritt: Maßerfassung mit Henning**
• Ort: {location}
• Datum: {due_date}
• Uhrzeit: {due_time}
• Henning bringt Stoffmuster mit
• Dauer: ca. 30-45 Minuten

Ich bestätige Ihren Termin und sende Ihnen alle Details per E-Mail zu."""

            messages = list(state.get("messages", []))
            messages.append({"role": "assistant", "content": summary_message, "sender": "design_henk"})

            return {
                "messages": messages,
                "session_state": session_state,
                "awaiting_user_input": True,
                "next_step": None,
                "metadata": {"appointment_confirmed": True, "location": location},
            }

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


async def image_policy_node(state: HenkGraphState) -> HenkGraphState:
    action_data = state.get("next_step")
    if not action_data:
        return {"image_policy": None}

    action = HandoffAction.model_validate(action_data)
    if action.kind != "tool" or action.name not in {"dalle_mood_board", "dalle_tool"}:
        return {"image_policy": state.get("image_policy")}

    session_state = _session_state(state)
    user_message = _latest_content(state.get("messages", []), "user") or state.get("user_input", "")

    decision = await ImagePolicyAgent().decide(
        user_message=user_message,
        state=session_state,
        supervisor_allows_dalle=True,
    )

    updates: Dict[str, Any] = {"image_policy": decision.model_dump()}

    if decision.allowed_source != "dalle":
        messages = list(state.get("messages", []))
        if decision.allowed_source == "rag":
            text = "Ich nutze echte Stoffbilder aus dem Katalog statt illustrativer Moodboards."
        elif decision.allowed_source == "upload":
            text = "Ich nutze deine hochgeladenen Stoffbilder für die Visualisierung."
        else:
            text = "Ohne reale Stoffbilder kann ich kein Moodboard zeigen. Bitte lade ein Stofffoto hoch oder wähle einen Stoff aus dem Katalog."
        messages.append({"role": "assistant", "content": text, "sender": "image_policy"})
        updates.update(
            {
                "messages": messages,
                "awaiting_user_input": True,
                "next_step": None,
            }
        )

    return updates


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
