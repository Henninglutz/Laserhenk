"""
Workflow Node Functions

Alle Node-Funktionen für den LangGraph Workflow.
Jede Funktion repräsentiert einen Schritt im Workflow.

Nodes:
- validate_query_node: Validiert User-Input
- smart_operator_node: Intelligentes Routing via Supervisor
- conversation_node: Führt Agent-Konversation aus
- tools_dispatcher_node: Dispatched zu verschiedenen Tools
"""

import os
from typing import Dict, Any, Optional
import logging

from agents.operator import OperatorAgent
from agents.supervisor_agent import SupervisorAgent, SupervisorDecision
from agents.henk1 import Henk1Agent
from agents.design_henk import DesignHenkAgent
from agents.laserhenk import LaserHenkAgent
from models.customer import Measurements, SessionState
from workflow.graph_state import HenkGraphState

logger = logging.getLogger(__name__)

# ==================== Singleton Instances ====================
# Agents werden nur einmal initialisiert für Performance

_supervisor: SupervisorAgent = None
_agent_instances: Dict[str, Any] = {}


def get_supervisor() -> SupervisorAgent:
    """
    Singleton Supervisor Agent.

    Returns:
        SupervisorAgent Instanz (wird nur einmal erstellt)
    """
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
        logger.info("[Singleton] SupervisorAgent created")
    return _supervisor


def get_agent(agent_name: str):
    """
    Factory für Agent-Instanzen mit Caching.

    Erstellt Agents lazy (nur wenn gebraucht) und cached sie.

    Args:
        agent_name: Name des Agents ("henk1", "design_henk", etc.)

    Returns:
        Agent-Instanz oder None wenn unbekannt
    """
    global _agent_instances

    if agent_name not in _agent_instances:
        if agent_name == "henk1":
            _agent_instances[agent_name] = Henk1Agent()
            logger.info("[Singleton] Henk1Agent created")
        elif agent_name == "design_henk":
            _agent_instances[agent_name] = DesignHenkAgent()
            logger.info("[Singleton] DesignHenkAgent created")
        elif agent_name == "laserhenk":
            _agent_instances[agent_name] = LaserHenkAgent()
            logger.info("[Singleton] LaserHenkAgent created")
        else:
            logger.warning(f"[Factory] Unknown agent: {agent_name}")
            return None

    return _agent_instances.get(agent_name)


# ==================== Node Functions ====================


async def validate_query_node(state: HenkGraphState) -> HenkGraphState:
    """
    Validiert User-Input vor Verarbeitung.

    Checks:
    - Minimale Länge (≥3 Zeichen)
    - Optional: Profanity Filter
    - Optional: Rate Limiting

    Args:
        state: Aktueller Graph State

    Returns:
        Updated State mit is_valid Flag
    """
    user_input = state.get("user_input", "")

    messages = list(state.get("messages", []))

    # Basis-Check: Minimale Länge
    if not user_input or len(user_input.strip()) < 3:
        messages.append(
            {
                "role": "system",
                "content": "Eingabe zu kurz. Bitte mindestens 3 Zeichen eingeben.",
                "sender": "validator",
                "timestamp": None,
            }
        )
        logger.warning(f"[Validator] Rejected: '{user_input}' (too short)")
        return {"is_valid": False, "messages": messages, "awaiting_user_input": True}

    # TODO: Weitere Validierungen
    # - Profanity Filter
    # - Spam Detection
    # - Rate Limiting (via session_id)

    logger.info(f"[Validator] Approved: '{user_input[:50]}...'")
    return {"is_valid": True, "messages": messages}


async def smart_operator_node(state: HenkGraphState) -> HenkGraphState:
    """
    Intelligenter Operator mit LLM (Supervisor).

    Der Supervisor analysiert User-Intent und routet flexibel zu:
    - Agents (henk1, design_henk, laserhenk)
    - Tools (rag_tool, comparison_tool, pricing_tool)
    - Clarification (bei Unklarheit)
    - End (bei Gesprächsende)

    Dies ist das "Gehirn" des Routing-Systems.

    Args:
        state: Aktueller Graph State

    Returns:
        Updated State mit next_agent und routing metadata
    """
    user_input = state.get("user_input", "")
    session_state = state["session_state"]
    conversation_history = state["messages"]

    # CRITICAL: If no user_input (after tool/agent execution), wait for new input
    # Don't route with empty message - this prevents infinite loops
    if not user_input or not user_input.strip():
        logger.info("[SmartOperator] No user_input, waiting for user response")
        messages = list(state.get("messages", []))

        # Check if there's a recent assistant response to show user
        recent_assistant = [msg for msg in messages[-3:] if msg.get("role") == "assistant"]

        if recent_assistant:
            # We have responses to show, just wait for user
            logger.info("[SmartOperator] Recent responses available, ending turn for user input")
            return {
                "next_agent": "end",
                "awaiting_user_input": True,
            }
        else:
            # No responses, something went wrong - ask clarification
            logger.warning("[SmartOperator] No user_input and no recent responses")
            messages.append({
                "role": "assistant",
                "content": "Wie kann ich dir weiterhelfen?",
                "sender": "supervisor",
            })
            return {
                "next_agent": "end",
                "messages": messages,
                "awaiting_user_input": True,
            }

    logger.info(f"[SmartOperator] Analyzing: '{user_input[:60]}...'")

    # Supervisor trifft Entscheidung (mit Offline-Fallback, damit Tests ohne API-Key laufen)
    if not os.environ.get("OPENAI_API_KEY"):
        logger.info("[SmartOperator] Offline routing fallback (no OPENAI_API_KEY)")
        operator = OperatorAgent()
        op_decision = await operator.process(session_state)
        decision = SupervisorDecision(
            next_destination=op_decision.next_agent or "end",
            reasoning="Rule-based fallback routing",
            action_params=op_decision.action_params or {},
            user_message=op_decision.message,
            confidence=1.0,
        )
    else:
        supervisor = get_supervisor()
        decision = await supervisor.decide_next_step(
            user_input,
            session_state.model_dump() if isinstance(session_state, SessionState) else session_state,
            conversation_history,
        )

    metadata = dict(state.get("metadata", {}))
    metadata["supervisor_reasoning"] = decision.reasoning
    metadata["confidence"] = decision.confidence

    updates: Dict[str, Any] = {
        "next_agent": decision.next_destination,
        "current_agent": decision.next_destination,
        "pending_action": decision.action_params,
        "metadata": metadata,
    }

    # Bei clarification oder end: Sofort Rückfrage/Abschlussnachricht an User
    if decision.next_destination in ["clarification", "end"] and decision.user_message:
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": "assistant",
                "content": decision.user_message,
                "sender": "supervisor",
                "metadata": {
                    "reasoning": decision.reasoning,
                    "confidence": decision.confidence,
                },
            }
        )
        updates["messages"] = messages
        updates["awaiting_user_input"] = True

    logger.info(
        f"[SmartOperator] Routed to '{decision.next_destination}' "
        f"(confidence={decision.confidence:.2f})"
    )

    return updates


async def conversation_node(state: HenkGraphState) -> HenkGraphState:
    """
    Führt Konversation mit aktuellem Agent aus.

    Entscheidet dynamisch ob:
    - LLM-basierte Konversation (process_with_llm)
    - Rule-based Processing (process)

    Diese Entscheidung trifft der Agent selbst via needs_llm() Methode.

    Args:
        state: Aktueller Graph State

    Returns:
        Updated State mit Agent-Response
    """
    current_agent_name = state["current_agent"]
    user_input = state.get("user_input", "")
    session_state = state["session_state"]

    if isinstance(session_state, dict):
        session_state = SessionState(**session_state)

    logger.info(f"[Conversation] Processing with agent='{current_agent_name}'")

    agent = get_agent(current_agent_name)

    if not agent:
        logger.error(f"[Conversation] Unknown agent: {current_agent_name}")
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": "system",
                "content": "Interner Fehler: Agent nicht gefunden.",
                "sender": "system",
            }
        )
        return {
            "next_agent": "clarification",
            "messages": messages,
            "awaiting_user_input": True,
        }

    # Sync messages from graph state to session_state.conversation_history
    messages = state.get("messages", [])
    session_state.conversation_history = messages

    try:
        decision = await agent.process(session_state)

        updated_session_state = session_state.model_copy()

        # Handle RAG query action - route to rag_tool
        if decision.action == "query_rag":
            logger.info(f"[Conversation] Agent {current_agent_name} requested RAG query, routing to rag_tool")

            # Mark that RAG will be queried for this agent
            if current_agent_name == "henk1":
                updated_session_state.henk1_rag_queried = True
            if current_agent_name == "design_henk":
                updated_session_state.design_rag_queried = True

            messages = list(state.get("messages", []))
            # Only add message if agent provided one (don't show internal routing messages)
            if decision.message and decision.message.strip():
                messages.append(
                    {
                        "role": "assistant",
                        "content": decision.message,
                        "sender": current_agent_name,
                        "metadata": {"action": decision.action},
                    }
                )

            # Route to rag_tool with query parameters
            return {
                "session_state": updated_session_state,
                "current_agent": current_agent_name,
                "next_agent": "rag_tool",
                "pending_action": decision.action_params or {},
                "awaiting_user_input": False,
                "phase_complete": False,
                "messages": messages,
            }

        # Handle DALL-E mood board generation (HENK1)
        if decision.action == "generate_mood_board":
            logger.info(f"[Conversation] Agent {current_agent_name} requested mood board generation")

            # Mark that mood board will be shown
            updated_session_state.henk1_mood_board_shown = True

            messages = list(state.get("messages", []))
            if decision.message and decision.message.strip():
                messages.append(
                    {
                        "role": "assistant",
                        "content": decision.message,
                        "sender": current_agent_name,
                        "metadata": {"action": decision.action},
                    }
                )

            # Route to dalle_tool with mood board parameters
            return {
                "session_state": updated_session_state,
                "current_agent": current_agent_name,
                "next_agent": "dalle_mood_board",
                "pending_action": decision.action_params or {},
                "awaiting_user_input": False,
                "phase_complete": False,
                "messages": messages,
            }

        # Handle DALL-E outfit visualization (Design Henk)
        if decision.action == "generate_image":
            logger.info(f"[Conversation] Agent {current_agent_name} requested outfit image generation")

            messages = list(state.get("messages", []))
            if decision.message and decision.message.strip():
                messages.append(
                    {
                        "role": "assistant",
                        "content": decision.message,
                        "sender": current_agent_name,
                        "metadata": {"action": decision.action},
                    }
                )

            # Route to dalle_tool with outfit visualization parameters
            return {
                "session_state": updated_session_state,
                "current_agent": current_agent_name,
                "next_agent": "dalle_outfit",
                "pending_action": decision.action_params or {},
                "awaiting_user_input": False,
                "phase_complete": False,
                "messages": messages,
            }

        # Handle fabric image display (HENK1 - shows real fabric images from RAG)
        if decision.action == "show_fabric_images":
            logger.info(f"[Conversation] Agent {current_agent_name} requested fabric image display")

            messages = list(state.get("messages", []))
            if decision.message and decision.message.strip():
                messages.append(
                    {
                        "role": "assistant",
                        "content": decision.message,
                        "sender": current_agent_name,
                        "metadata": {"action": decision.action},
                    }
                )

            # Route to show_fabric_images tool
            return {
                "session_state": updated_session_state,
                "current_agent": current_agent_name,
                "next_agent": "show_fabric_images",
                "pending_action": decision.action_params or {},
                "awaiting_user_input": False,
                "phase_complete": False,
                "messages": messages,
            }

        # Handle other special actions
        if current_agent_name == "henk1" and not updated_session_state.customer.customer_id:
            updated_session_state.customer.customer_id = (
                f"TEMP_{updated_session_state.session_id[:8]}"
            )

        if decision.action == "request_saia_measurement":
            updated_session_state.measurements = updated_session_state.measurements or Measurements(
                measurement_id=f"MOCK_{updated_session_state.session_id[:8]}",
                source="saia",
            )
            updated_session_state.customer.has_measurements = True

        messages = list(state.get("messages", []))

        # Only add agent message if there is actual content to show user
        # Don't add generic fallback messages for internal state transitions
        if decision.message and decision.message.strip():
            messages.append(
                {
                    "role": "assistant",
                    "content": decision.message,
                    "sender": current_agent_name,
                    "metadata": {"action": decision.action},
                }
            )

        updates = {
            "session_state": updated_session_state,
            "current_agent": current_agent_name,
            "next_agent": decision.next_agent,
            "pending_action": decision.action_params or {},
            "awaiting_user_input": not decision.should_continue,
            "phase_complete": not decision.should_continue,
            "messages": messages,
        }

        logger.info(
            f"[Conversation] Decision: next_agent='{decision.next_agent}', "
            f"should_continue={decision.should_continue}"
        )

    except Exception as e:
        logger.error(f"[Conversation] Agent failed: {e}", exc_info=True)

        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": "assistant",
                "content": "Entschuldigung, ich hatte ein Problem. Kannst du das nochmal sagen?",
                "sender": current_agent_name,
            }
        )
        return {
            "next_agent": "clarification",
            "messages": messages,
            "awaiting_user_input": True,
        }

    return updates


async def tools_dispatcher_node(state: HenkGraphState) -> HenkGraphState:
    """
    Dispatcher für verschiedene Tools.

    Unterstützt:
    - rag_tool: Stoff-/Bild-Suche via RAG
    - comparison_tool: Vergleiche zwischen Optionen
    - pricing_tool: Preiskalkulation

    Args:
        state: Aktueller Graph State

    Returns:
        Updated State mit Tool-Result
    """
    next_agent = state["next_agent"]
    action_params = state.get("pending_action") or {}
    current_agent = state.get("current_agent")

    logger.info(
        f"[ToolsDispatcher] Executing tool='{next_agent}' with params={action_params}"
    )

    messages = list(state.get("messages", []))

    try:
        if next_agent == "rag_tool":
            # Capture lead when customer requests fabric information
            await _capture_lead_if_needed(state, trigger="rag_query")
            result = await _execute_rag_tool(action_params, state)
            messages.append({"role": "assistant", "content": result, "sender": next_agent})

        elif next_agent == "dalle_mood_board":
            # Capture lead when generating mood board (shows high engagement)
            await _capture_lead_if_needed(state, trigger="mood_board_generation")
            result, image_url = await _execute_dalle_mood_board(action_params, state)
            messages.append({
                "role": "assistant",
                "content": result,
                "sender": next_agent,
                "metadata": {"image_url": image_url} if image_url else {}
            })
            # Store image URL in session state
            if image_url:
                session_state = state["session_state"]
                if isinstance(session_state, dict):
                    session_state = SessionState(**session_state)
                session_state.mood_image_url = image_url
                # Add to generation history
                session_state.image_generation_history.append({
                    "url": image_url,
                    "type": "mood_board",
                    "timestamp": str(state.get("metadata", {}).get("timestamp")),
                    "approved": False,
                })
                state["session_state"] = session_state

        elif next_agent == "generate_outfit" or next_agent == "dalle_outfit":
            # Generate photorealistic outfit visualization with selected fabric
            await _capture_lead_if_needed(state, trigger="outfit_visualization")
            result, image_url = await _execute_outfit_visualization(action_params, state)
            messages.append({
                "role": "assistant",
                "content": result,
                "sender": next_agent,
                "metadata": {"image_url": image_url} if image_url else {}
            })
            # Store image URL in session state
            if image_url:
                session_state = state["session_state"]
                if isinstance(session_state, dict):
                    session_state = SessionState(**session_state)
                session_state.mood_image_url = image_url
                # Add to generation history
                session_state.image_generation_history.append({
                    "url": image_url,
                    "type": "outfit_visualization",
                    "timestamp": str(state.get("metadata", {}).get("timestamp")),
                    "approved": False,
                })
                state["session_state"] = session_state

        elif next_agent == "show_fabric_images":
            # Capture lead when showing fabric images (customer is engaged)
            await _capture_lead_if_needed(state, trigger="fabric_image_view")
            result, fabric_images = await _execute_show_fabric_images(action_params, state)
            # fabric_images is a list of dicts with url, fabric_code, name, etc.
            metadata = {}
            if fabric_images:
                # Store multiple fabric images in metadata
                metadata["fabric_images"] = fabric_images
                # Also store first image as primary image_url for backward compatibility
                metadata["image_url"] = fabric_images[0]["url"]

            messages.append({
                "role": "assistant",
                "content": result,
                "sender": next_agent,
                "metadata": metadata
            })

            # Store fabric images in session state
            if fabric_images:
                session_state = state["session_state"]
                if isinstance(session_state, dict):
                    session_state = SessionState(**session_state)
                # Store in session for later reference
                for img in fabric_images:
                    session_state.image_generation_history.append({
                        "url": img["url"],
                        "type": "fabric_image",
                        "fabric_code": img["fabric_code"],
                        "timestamp": str(state.get("metadata", {}).get("timestamp")),
                        "approved": False,
                    })
                state["session_state"] = session_state

        elif next_agent == "comparison_tool":
            result = await _execute_comparison_tool(action_params, state)
            messages.append({"role": "assistant", "content": result, "sender": next_agent})

        elif next_agent == "pricing_tool":
            result = await _execute_pricing_tool(action_params, state)
            messages.append({"role": "assistant", "content": result, "sender": next_agent})

        else:
            logger.warning(f"[ToolsDispatcher] Unknown tool: {next_agent}")
            result = "Tool nicht gefunden."
            messages.append({"role": "assistant", "content": result, "sender": next_agent})

        logger.info(f"[ToolsDispatcher] Tool '{next_agent}' executed successfully")

    except Exception as e:
        logger.error(f"[ToolsDispatcher] Tool failed: {e}", exc_info=True)

        messages.append(
            {
                "role": "assistant",
                "content": f"Entschuldigung, das Tool '{next_agent}' hatte ein Problem.",
                "sender": next_agent,
            }
        )

    # CRITICAL FIX: After tool execution, return to the agent that requested the tool
    # NOT to supervisor with the old user_input (which would cause loops)
    return_to_agent = current_agent if current_agent in ["henk1", "design_henk", "laserhenk"] else None

    if return_to_agent:
        logger.info(f"[ToolsDispatcher] Returning to agent '{return_to_agent}' after tool execution")
        return {
            "messages": messages,
            "next_agent": return_to_agent,
            "current_agent": return_to_agent,
            "awaiting_user_input": False,  # Continue workflow, don't wait
            "user_input": None,  # Clear user_input to prevent re-processing
        }
    else:
        # No specific agent to return to, wait for user input
        logger.info("[ToolsDispatcher] No agent to return to, awaiting user input")
        return {
            "messages": messages,
            "awaiting_user_input": True,
            "user_input": None,  # Clear user_input
        }


# ==================== Tool Implementations ====================


async def _capture_lead_if_needed(state: HenkGraphState, trigger: str) -> None:
    """
    Capture lead in CRM if customer shows engagement.

    Args:
        state: Graph state with session and customer data
        trigger: What triggered the lead capture (e.g., "rag_query", "image_generation")
    """
    from tools.crm_tool import CRMTool
    from models.tools import CRMLeadCreate

    try:
        session_state = state.get("session_state")
        if isinstance(session_state, dict):
            session_state = SessionState(**session_state)

        # Check if lead already captured for this session
        if getattr(session_state, "lead_captured", False):
            logger.info(f"[LeadCapture] Lead already captured for session {session_state.session_id}")
            return

        # Extract customer info from session
        customer = session_state.customer

        # Extract structured preferences
        preferences = getattr(session_state, "customer_preferences", {})

        # Build structured notes
        notes_parts = []

        # Add occasion if available
        if preferences.get("occasion"):
            notes_parts.append(f"Anlass: {preferences['occasion']}")

        # Add colors if available
        if preferences.get("colors"):
            colors_str = ", ".join(preferences["colors"])
            notes_parts.append(f"Farbwünsche: {colors_str}")

        # Add style keywords
        if preferences.get("style_keywords"):
            style_str = ", ".join(preferences["style_keywords"])
            notes_parts.append(f"Stil: {style_str}")

        # Add budget if available
        if preferences.get("budget"):
            notes_parts.append(f"Budget: {preferences['budget']}")

        # Add selected fabric if user has chosen one
        if preferences.get("selected_fabric_code"):
            fabric_info = f"{preferences['selected_fabric_name']} ({preferences['selected_fabric_code']})"
            notes_parts.append(f"Gewählter Stoff: {fabric_info}")
            notes_parts.append(f"Farbe: {preferences.get('selected_fabric_color', 'N/A')}")

        # Add selected fabrics from rag_context
        rag_context = getattr(session_state, "rag_context", {}) or {}
        if rag_context and rag_context.get("fabrics"):
            fabric_count = len(rag_context["fabrics"])
            notes_parts.append(f"Stoffoptionen angezeigt: {fabric_count}")

        # Add trigger information
        notes_parts.append(f"Lead-Trigger: {trigger}")

        # Fallback: Add conversation snippet if no structured data
        if not notes_parts:
            conversation_text = " ".join(
                msg.get("content", "")
                for msg in state.get("messages", [])
                if isinstance(msg, dict) and msg.get("role") == "user"
            )
            notes_parts.append(f"Conversation: {conversation_text[:200]}...")

        structured_notes = "\n".join(notes_parts)

        # Create lead data with structured information
        # In production, you'd collect email via a form
        lead_data = CRMLeadCreate(
            customer_name=customer.customer_id or f"Lead_{session_state.session_id[:8]}",
            email=f"temp_{session_state.session_id[:8]}@laserhenk.com",  # Temporary
            phone=None,
            source=f"HENK1_Chatbot_{trigger}",
            notes=structured_notes,
            deal_value=0.0,  # Will be updated later
        )

        # Create lead
        crm = CRMTool()
        response = await crm.create_lead(lead_data)

        if response.success:
            logger.info(f"[LeadCapture] Lead created: {response.lead_id} (trigger={trigger})")
            # Mark lead as captured
            session_state.lead_captured = True
            state["session_state"] = session_state
        else:
            logger.warning(f"[LeadCapture] Failed to create lead: {response.message}")

    except Exception as e:
        logger.error(f"[LeadCapture] Error capturing lead: {e}", exc_info=True)
        # Don't fail workflow if lead capture fails


async def _execute_rag_tool(params: Dict[str, Any], state: HenkGraphState) -> str:
    """
    RAG Tool: Sucht Stoffe/Bilder via Vector Search.

    Args:
        params: Suchparameter (query, colors, patterns, season, etc.)
        state: Graph State für Context

    Returns:
        Formatierte Suchergebnisse mit Stoff-Empfehlungen
    """
    from tools.rag_tool import RAGTool
    from models.fabric import FabricSearchCriteria

    query = params.get("query", "")
    logger.info(f"[RAGTool] Executing fabric search with params={params}")

    # Build search criteria from parameters
    # Extract colors, patterns from query if provided, or use defaults
    colors = params.get("colors", [])
    patterns = params.get("patterns", [])

    # If no specific criteria, create basic search
    criteria = FabricSearchCriteria(
        colors=colors if colors else [],
        patterns=patterns if patterns else [],
        limit=10,
    )

    rag = RAGTool()
    try:
        recommendations = await rag.search_fabrics(criteria)

        # Format Results
        if not recommendations:
            return """Hmm, ich habe gerade keine passenden Stoffe in der Datenbank gefunden.

Das kann daran liegen, dass die Datenbank noch nicht vollständig gefüllt ist.

**Was ich für dich tun kann:**
- Gib mir mehr Details zu deinen Wünschen (Farbe, Muster, Anlass)
- Oder lass uns direkt über Design und Schnitt sprechen

Wie möchtest du weitermachen? 🎩"""

        # Store RAG results in session state for later use (e.g., fabric image display)
        session_state = state.get("session_state")
        if isinstance(session_state, dict):
            session_state = SessionState(**session_state)

        # Store fabric recommendations for potential image display
        session_state.rag_context = {
            "fabrics": [
                {
                    "fabric_code": rec.fabric.fabric_code,
                    "name": rec.fabric.name,
                    "color": rec.fabric.color,
                    "pattern": rec.fabric.pattern,
                    "composition": rec.fabric.composition,
                    "weight": rec.fabric.weight,
                    "image_urls": rec.fabric.image_urls,
                    "local_image_paths": rec.fabric.local_image_paths,
                    "similarity_score": rec.similarity_score,
                }
                for rec in recommendations[:10]
            ],
            "query": query,
            "colors": colors,
            "patterns": patterns,
        }
        state["session_state"] = session_state

        # Show only 2-3 fabrics for initial selection
        initial_limit = min(3, len(recommendations))

        formatted = "**Passende Stoffe für deinen Anzug:**\n\n"
        for i, rec in enumerate(recommendations[:initial_limit], 1):
            fabric = rec.fabric
            formatted += f"**{i}. {fabric.name or 'Hochwertiger Stoff'}**\n"
            formatted += f"   🏷️ Code: {fabric.fabric_code}\n"
            formatted += f"   📦 Material: {fabric.composition or 'Edle Wollmischung'}\n"
            formatted += f"   🎨 Farbe: {fabric.color or 'Klassisch'}\n"
            formatted += f"   ✨ Muster: {fabric.pattern or 'Uni'}\n"
            formatted += f"   ⚖️ Gewicht: {fabric.weight or '260-280g/m²'}\n"

            # Add similarity score if high
            if rec.similarity_score > 0.8:
                formatted += f"   💯 Sehr gute Übereinstimmung ({rec.similarity_score:.0%})\n"

            formatted += "\n"

        if len(recommendations) > initial_limit:
            formatted += f"_({len(recommendations) - initial_limit} weitere Optionen verfügbar auf Wunsch)_\n\n"

        formatted += "**Moment, ich zeige dir die Stoffe visuell! 🎨**"

        return formatted

    except Exception as e:
        logger.error(f"[RAGTool] Error during fabric search: {e}", exc_info=True)
        return """Entschuldigung, beim Abrufen der Stoffe gab es ein technisches Problem.

Lass uns trotzdem weitermachen – ich kann dir auch ohne Datenbank bei der Auswahl helfen!

Was ist dir wichtig bei deinem Anzug? 🎩"""

    finally:
        await rag.close()


async def _execute_comparison_tool(
    params: Dict[str, Any], state: HenkGraphState
) -> str:
    """
    Comparison Tool: Vergleicht Optionen (Stoffe, Designs, etc.).

    Args:
        params: Vergleichsparameter (items, comparison_type)
        state: Graph State für Context

    Returns:
        Vergleichstabelle
    """
    items = params.get("items", [])
    comparison_type = params.get("comparison_type", "general")

    logger.info(
        f"[ComparisonTool] Comparing {len(items)} items of type '{comparison_type}'"
    )

    if len(items) < 2:
        return "Ich brauche mindestens 2 Optionen zum Vergleichen."

    # TODO: Implement actual comparison logic
    return f"""**Vergleich ({comparison_type}):**

Option 1: {items[0]}
Option 2: {items[1]}

_[Detaillierter Vergleich wird noch implementiert]_"""


async def _execute_dalle_mood_board(
    params: Dict[str, Any], state: HenkGraphState
) -> tuple[str, Optional[str]]:
    """
    DALL-E Mood Board Tool: Generiert Composite Mood Board mit echten Stoffbildern.

    WICHTIG: Erstellt Composite-Bild:
    1. Holt Stoffdaten aus rag_context (falls vorhanden)
    2. DALL-E generiert Mood Board basierend auf Stoffbeschreibungen + Anlass
    3. Echte Stofffotos werden als Thumbnails (10%) unten rechts eingefügt

    Args:
        params: Generation-Parameter (style_keywords, colors, occasion, session_id)
        state: Graph State mit optional rag_context

    Returns:
        Tuple of (formatted_message, composite_image_url)
    """
    from tools.dalle_tool import get_dalle_tool

    style_keywords = params.get("style_keywords", [])
    occasion = params.get("occasion", "elegant occasion")
    session_id = params.get("session_id")

    logger.info(
        f"[DALLE_MoodBoard] Generating composite mood board: "
        f"style={style_keywords}, occasion={occasion}"
    )

    # Extract fabrics from rag_context if available
    session_state = state.get("session_state")
    if isinstance(session_state, dict):
        session_state = SessionState(**session_state)

    rag_context = getattr(session_state, "rag_context", {})
    fabrics = rag_context.get("fabrics", [])

    if not fabrics:
        logger.warning("[DALLE_MoodBoard] No fabrics in rag_context, cannot create composite")
        message = """Moment – ich brauche erst Stoffempfehlungen, um ein passendes Mood Board zu erstellen.

Lass uns zuerst Stoffe auswählen! Welche Farben und Muster interessieren dich? 🎩"""
        return message, None

    try:
        dalle = get_dalle_tool()
        response = await dalle.generate_mood_board_with_fabrics(
            fabrics=fabrics[:5],  # Top 5 fabrics
            occasion=occasion,
            style_keywords=style_keywords,
            session_id=session_id,
        )

        if response.success and response.image_url:
            logger.info(f"[DALLE_MoodBoard] Composite created: {response.image_url}")

            # Get fabric names for message
            fabric_names = [f.get("name", "Hochwertiger Stoff") for f in fabrics[:5]]

            # Build fabric list for message
            fabric_list = "\n".join(f"- **{name}**" for name in fabric_names)

            message = f"""🎨 **Dein Mood Board ist fertig!**

Ich zeige dir die Top {len(fabric_names)} Stoffe in ihrer perfekten Umgebung:
{fabric_list}

Die kleinen Stoffbilder unten rechts zeigen die echten Referenzen! 📸

**Was denkst du?** Welche Stoffe gefallen dir am besten? 🎩"""

            return message, response.image_url

        else:
            logger.error(f"[DALLE_MoodBoard] Failed: {response.error}")
            message = """Entschuldigung, beim Erstellen des Mood Boards gab es ein Problem.

Lass uns trotzdem weitermachen – ich beschreibe dir die Stoffe! 🎩"""
            return message, None

    except Exception as e:
        logger.error(f"[DALLE_MoodBoard] Exception: {e}", exc_info=True)
        message = """Entschuldigung, das Mood Board konnte gerade nicht generiert werden.

Macht nichts – lass uns über die Stoffe sprechen! 🎩"""
        return message, None


async def _execute_outfit_visualization(
    params: Dict[str, Any], state: HenkGraphState
) -> tuple[str, Optional[str]]:
    """
    DALL-E Outfit Visualization: Generates photorealistic suit visualization with selected fabric.

    **NEW WORKFLOW:**
    - User selects ONE fabric from 2-3 options
    - DALL-E generates photorealistic suit/outfit wearing this fabric
    - Background shows the occasion context (wedding, business, etc.)
    - Foreground shows detailed suit with fabric texture
    - Small fabric swatch reference in corner

    Args:
        params: Generation parameters
            - fabric_data: Selected fabric dict (name, color, pattern, composition, image_url)
            - occasion: Occasion type (wedding, business, gala, etc.)
            - style_keywords: Style descriptors
            - session_id: Session ID for caching

    Returns:
        Tuple of (formatted_message, image_url)
    """
    from tools.dalle_tool import get_dalle_tool

    fabric_data = params.get("fabric_data", {})
    occasion = params.get("occasion", "elegant occasion")
    style_keywords = params.get("style_keywords", [])
    session_id = params.get("session_id")

    if not fabric_data:
        logger.warning("[OutfitVisualization] No fabric data provided")
        return "Ich brauche erst eine Stoffauswahl, um das Outfit zu visualisieren.", None

    fabric_name = fabric_data.get("name", "Hochwertiger Stoff")
    fabric_code = fabric_data.get("fabric_code", "")
    fabric_color = fabric_data.get("color", "classic")
    fabric_pattern = fabric_data.get("pattern", "solid")
    fabric_composition = fabric_data.get("composition", "fine wool")

    logger.info(
        f"[OutfitVisualization] Generating outfit with fabric: {fabric_name} ({fabric_code}), "
        f"occasion: {occasion}"
    )

    try:
        dalle = get_dalle_tool()

        # Build photorealistic outfit prompt
        prompt = _build_outfit_prompt(
            fabric_color=fabric_color,
            fabric_pattern=fabric_pattern,
            fabric_composition=fabric_composition,
            occasion=occasion,
            style_keywords=style_keywords,
        )

        # Generate outfit image
        from models.tools import DALLEImageRequest
        response = await dalle.generate_image(
            DALLEImageRequest(
                prompt=prompt,
                size="1024x1024",
                quality="hd",  # Use HD quality for photorealistic output
            )
        )

        if response.success and response.image_url:
            logger.info(f"[OutfitVisualization] Success: {response.image_url}")

            message = f"""✨ **Dein Anzug-Entwurf ist fertig!**

So würde dein maßgeschneiderter Anzug mit **{fabric_name}** aussehen:

📦 **Stoff-Details:**
   • Farbe: {fabric_color}
   • Muster: {fabric_pattern}
   • Material: {fabric_composition}
   • Ref: {fabric_code}

🎯 **Anlass:** {occasion}

**Gefällt dir die Richtung?**

Wir können Details anpassen oder einen anderen Stoff wählen! 🎩"""

            return message, response.image_url

        else:
            logger.error(f"[OutfitVisualization] Failed: {response.error}")
            message = f"""Entschuldigung, beim Erstellen der Visualisierung gab es ein Problem.

Aber lass uns trotzdem weitermachen – ich kann dir beschreiben, wie **{fabric_name}** in deinem Anzug aussehen würde! 🎩"""
            return message, None

    except Exception as e:
        logger.error(f"[OutfitVisualization] Exception: {e}", exc_info=True)
        message = f"""Entschuldigung, die Visualisierung konnte gerade nicht erstellt werden.

Kein Problem – wir machen trotzdem weiter mit **{fabric_name}**! 🎩"""
        return message, None


def _build_outfit_prompt(
    fabric_color: str,
    fabric_pattern: str,
    fabric_composition: str,
    occasion: str,
    style_keywords: list[str],
) -> str:
    """
    Build photorealistic outfit prompt for DALL-E.

    Creates detailed prompt for generating realistic suit visualization
    with fabric texture and occasion-appropriate background.

    Args:
        fabric_color: Fabric color (e.g., "Navy", "Grey", "Blue")
        fabric_pattern: Fabric pattern (e.g., "Solid", "Pinstripe", "Herringbone")
        fabric_composition: Fabric material (e.g., "100% Wool", "Wool/Silk blend")
        occasion: Occasion type (e.g., "Hochzeit", "Business", "Gala")
        style_keywords: Style descriptors (e.g., ["modern", "elegant"])

    Returns:
        Detailed DALL-E prompt for photorealistic outfit generation
    """
    # Map occasion to background setting
    occasion_backgrounds = {
        "Hochzeit": "elegant wedding venue with soft natural lighting, romantic garden or modern reception hall",
        "wedding": "elegant wedding venue with soft natural lighting, romantic garden or modern reception hall",
        "Business": "modern executive office with floor-to-ceiling windows, professional corporate environment",
        "business": "modern executive office with floor-to-ceiling windows, professional corporate environment",
        "Gala": "luxury ballroom with chandeliers and marble floors, sophisticated evening event atmosphere",
        "gala": "luxury ballroom with chandeliers and marble floors, sophisticated evening event atmosphere",
        "Formal": "upscale formal venue with elegant architecture and refined ambiance",
        "formal": "upscale formal venue with elegant architecture and refined ambiance",
        "Casual": "contemporary urban setting with natural daylight, modern lifestyle environment",
        "casual": "contemporary urban setting with natural daylight, modern lifestyle environment",
    }

    background = occasion_backgrounds.get(occasion, "elegant professional setting with refined atmosphere")
    style_desc = ", ".join(style_keywords) if style_keywords else "timeless elegant"

    # Build fabric description
    pattern_desc = ""
    if fabric_pattern.lower() != "solid" and fabric_pattern.lower() != "plain":
        pattern_desc = f" with {fabric_pattern.lower()} pattern"

    fabric_desc = f"{fabric_color.lower()} {fabric_composition.lower()}{pattern_desc}"

    # Create detailed prompt
    prompt = f"""Create a photorealistic, professional menswear photography image showing a complete men's suit.

SUIT DETAILS:
- Fabric: {fabric_desc}
- Style: {style_desc}, bespoke tailoring, impeccable fit
- Cut: Modern tailored fit with structured shoulders
- Composition: Two-piece suit (jacket and trousers)

PRESENTATION:
- Show full suit on professional mannequin or hanger in premium boutique setting
- Focus on fabric texture and pattern details
- Show natural fabric drape and construction quality
- Professional lighting to highlight material quality

BACKGROUND:
- Setting: {background}
- Ambiance: Sophisticated, high-end, {occasion.lower()} appropriate
- Lighting: Natural, soft, professional photography lighting

STYLE:
- Professional fashion editorial photography
- Clean, elegant composition
- Focus on suit craftsmanship and fabric quality
- {style_desc} aesthetic

NOTE: Leave small bottom-right corner clear for fabric swatch reference overlay."""

    logger.info(f"[OutfitPrompt] Generated: {prompt[:150]}...")
    return prompt


async def _execute_dalle_outfit(
    params: Dict[str, Any], state: HenkGraphState
) -> tuple[str, Optional[str]]:
    """
    DEPRECATED: Use _execute_outfit_visualization() instead.

    Legacy DALL-E Outfit Visualization Tool.
    Kept for backward compatibility with Design Henk.
    """
    logger.warning("[DALLE_Outfit] Using deprecated _execute_dalle_outfit, routing to _execute_outfit_visualization")
    return await _execute_outfit_visualization(params, state)


async def _execute_show_fabric_images(
    params: Dict[str, Any], state: HenkGraphState
) -> tuple[str, Optional[list[dict]]]:
    """
    Show Fabric Images: Zeigt echte Stoffbilder aus RAG-Ergebnissen.

    WICHTIG: Verwendet ECHTE Stoffbilder aus der Datenbank, KEINE DALL-E Generation!

    Args:
        params: Display-Parameter (optional: limit, occasion)
        state: Graph State mit rag_context

    Returns:
        Tuple of (formatted_message, fabric_images_list)
        fabric_images_list = [{"url": str, "fabric_code": str, "name": str}, ...]
    """
    logger.info("[ShowFabricImages] Displaying real fabric images from RAG results")

    try:
        session_state = state.get("session_state")
        if isinstance(session_state, dict):
            session_state = SessionState(**session_state)

        # Get RAG context with fabric data
        rag_context = getattr(session_state, "rag_context", {})
        fabrics = rag_context.get("fabrics", [])

        if not fabrics:
            logger.warning("[ShowFabricImages] No fabrics in RAG context")
            message = """Hmm, ich habe keine Stoff-Daten gefunden.

Lass mich nochmal die Datenbank abfragen! Welche Farben interessieren dich? 🎩"""
            return message, None

        # Get limit from params (default 3 for initial selection)
        limit = params.get("limit", 3)

        # Get top N fabrics with images (2-3 for initial selection)
        fabrics_with_images = []
        for fabric in fabrics[:limit * 2]:  # Check double limit to find images
            image_urls = fabric.get("image_urls", [])
            local_paths = fabric.get("local_image_paths", [])

            # Prefer local paths, fallback to URLs
            image_url = None
            if local_paths and local_paths[0]:
                # Convert local path to web-accessible URL
                # Assuming images are in generated_images/ or a static folder
                local_path = local_paths[0]
                # TODO: Configure proper static file serving
                # For now, use the remote URL
                image_url = image_urls[0] if image_urls else None
            elif image_urls and image_urls[0]:
                image_url = image_urls[0]

            if image_url:
                fabrics_with_images.append({
                    "url": image_url,
                    "fabric_code": fabric.get("fabric_code", ""),
                    "name": fabric.get("name", "Hochwertiger Stoff"),
                    "color": fabric.get("color", ""),
                    "pattern": fabric.get("pattern", ""),
                    "composition": fabric.get("composition", ""),
                    "similarity_score": fabric.get("similarity_score", 0.0),
                })

            if len(fabrics_with_images) >= limit:
                break

        if not fabrics_with_images:
            logger.warning("[ShowFabricImages] No fabric images available")
            message = """Die Stoffbilder sind leider noch nicht verfügbar.

Aber ich kann dir die technischen Details zeigen – welcher Stoff interessiert dich am meisten? 🎩"""
            return message, None

        # Build message with fabric details
        occasion = params.get("occasion", "deinen Anlass")

        message = f"""🎨 **Hier sind {len(fabrics_with_images)} Stoff-Empfehlungen für {occasion}:**

"""

        for i, fabric in enumerate(fabrics_with_images, 1):
            message += f"""**{i}. {fabric['name']}** (Ref: {fabric['fabric_code']})
   🎨 Farbe: {fabric['color']}
   ✨ Muster: {fabric['pattern']}
   📦 Material: {fabric['composition']}

"""

        message += f"""**Welcher Stoff gefällt dir am besten?**

Sag mir einfach die Nummer (z.B. "Nummer 1"), dann zeige ich dir wie dein Anzug damit aussehen würde! 🎩

_(Du kannst auch nach mehr Optionen fragen)_"""

        logger.info(f"[ShowFabricImages] Returning {len(fabrics_with_images)} fabric images")
        return message, fabrics_with_images

    except Exception as e:
        logger.error(f"[ShowFabricImages] Exception: {e}", exc_info=True)
        message = """Entschuldigung, beim Laden der Stoffbilder gab es ein Problem.

Lass uns trotzdem weitermachen – ich beschreibe dir die Stoffe! 🎩"""
        return message, None


async def _execute_pricing_tool(params: Dict[str, Any], state: HenkGraphState) -> str:
    """
    Pricing Tool: Berechnet Preis basierend auf Customer-Daten und Stoff-Auswahl.

    Pricing Policy (aus henk_core_prompt):
    - "no_prices_before_fabric: true" - Preise erst NACH Stoffauswahl
    - "price_hint_on_demand: optional" - Nur auf Nachfrage

    Nutzt RAG für stoffbasierte Preise, wenn verfügbar.

    Args:
        params: Pricing-Parameter (optional: fabric_code, garment_type)
        state: Graph State mit customer_data

    Returns:
        Preisschätzung basierend auf Stoff + Konfig
    """
    from tools.rag_tool import RAGTool

    customer_data = state["session_state"].get("customer_data", {})
    fabric_code = params.get("fabric_code") or customer_data.get("selected_fabric")
    garment_type = params.get("garment_type") or customer_data.get(
        "garment_type", "suit"
    )

    logger.info(
        f"[PricingTool] Calculating price: fabric_code={fabric_code}, "
        f"garment_type={garment_type}, customer_data={list(customer_data.keys())}"
    )

    # Check: Hat User schon Stoff gewählt?
    if not fabric_code:
        logger.info("[PricingTool] No fabric selected - returning policy notice")
        return """**Preisauskunft:**

Gerne! Um dir einen genauen Preis zu nennen, brauche ich noch deine Stoffauswahl.

Die Stoffkategorie macht den größten Unterschied - von klassischer Schurwolle bis zu exklusiven italienischen Tüchern.

Soll ich dir passende Stoffe zeigen? Dann kann ich direkt den Preis kalkulieren."""

    # Versuche Stoff-Preis aus RAG zu holen
    fabric_price = None
    fabric_name = "Ausgewählter Stoff"

    try:
        rag = RAGTool()
        fabric_data = await rag.get_fabric_by_code(fabric_code)

        if fabric_data and "price" in fabric_data:
            fabric_price = fabric_data["price"]
            fabric_name = fabric_data.get("name", fabric_code)
            logger.info(f"[PricingTool] Got fabric price from RAG: {fabric_price}€")
    except Exception as e:
        logger.warning(f"[PricingTool] RAG lookup failed: {e}")

    # Fallback: Basis-Preise nach Garment Type
    if fabric_price is None:
        logger.info("[PricingTool] Using fallback pricing (RAG not available)")
        # Basis-Preise für Bespoke-Anfertigung
        base_prices = {
            "suit": 1800,  # 2-Teiler
            "three_piece": 2100,  # 3-Teiler
            "jacket": 1200,  # Sakko einzeln
            "trousers": 600,  # Hose einzeln
            "vest": 400,  # Weste einzeln
            "coat": 2500,  # Mantel
            "tuxedo": 2200,  # Smoking
        }
        fabric_price = base_prices.get(garment_type, 1800)

    # Adjustments basierend auf Konfiguration
    adjustments = []
    total = fabric_price

    # Extras
    if customer_data.get("monogram"):
        total += 50
        adjustments.append("+ 50€ Monogramm")

    if customer_data.get("custom_lining"):
        total += 150
        adjustments.append("+ 150€ Custom-Innenfutter")

    if customer_data.get("custom_buttons"):
        total += 80
        adjustments.append("+ 80€ Spezial-Knöpfe")

    # Three-piece upgrade
    if garment_type == "suit" and customer_data.get("add_vest"):
        total += 400
        adjustments.append("+ 400€ Weste")
        garment_type = "three_piece"

    # Format Output
    garment_labels = {
        "suit": "Bespoke-Anzug (2-teilig)",
        "three_piece": "Bespoke-Anzug (3-teilig)",
        "jacket": "Bespoke-Sakko",
        "trousers": "Bespoke-Hose",
        "vest": "Bespoke-Weste",
        "coat": "Bespoke-Mantel",
        "tuxedo": "Bespoke-Smoking",
    }

    result = f"""**Preiskalkulation:**

{garment_labels.get(garment_type, "Bespoke-Kleidungsstück")}
Stoff: {fabric_name}

Basis: {fabric_price}€"""

    if adjustments:
        result += "\n" + "\n".join(adjustments)

    result += f"""

**Gesamt: {total}€**

_Inkl. individueller Anpassung, Maßanfertigung und Premium-Service._
_Preis kann sich bei finaler Stoffauswahl/Details noch ändern._"""

    return result
