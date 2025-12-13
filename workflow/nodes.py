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
from datetime import datetime

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
    logger.info(f"[ToolsDispatcher] current_agent='{current_agent}' (will return here after tool execution)")

    messages = list(state.get("messages", []))

    try:
        if next_agent == "rag_tool":
            result, fabric_images = await _execute_rag_tool(action_params, state)

            # Build metadata with fabric_images
            metadata = {}
            if fabric_images:
                metadata["fabric_images"] = fabric_images
                # Also add first image as primary image_url for backward compatibility
                metadata["image_url"] = fabric_images[0]["url"]
                logger.info(f"[ToolsDispatcher] RAG returned {len(fabric_images)} fabric images")

            messages.append({
                "role": "assistant",
                "content": result,
                "sender": next_agent,
                "metadata": metadata
            })

        elif next_agent == "dalle_mood_board":
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

        elif next_agent == "dalle_outfit":
            result, image_url = await _execute_dalle_outfit(action_params, state)
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

        elif next_agent == "mark_favorite_fabric":
            result = await _execute_mark_favorite_fabric(action_params, state)
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


async def _execute_rag_tool(params: Dict[str, Any], state: HenkGraphState) -> tuple[str, Optional[list[dict]]]:
    """
    RAG Tool: Sucht Stoffe/Bilder via Vector Search.

    Args:
        params: Suchparameter (query, colors, patterns, season, etc.)
        state: Graph State für Context

    Returns:
        Tuple of (formatted_message, fabric_images_list)
        fabric_images_list = [{"url": str, "fabric_code": str, "name": str}, ...] or None
    """
    from tools.rag_tool import RAGTool
    from models.fabric import FabricSearchCriteria

    query = params.get("query", "")
    logger.info(f"[RAGTool] Executing fabric search with params={params}")

    # Build search criteria from parameters
    # Extract colors, patterns from query if provided, or use defaults
    colors = params.get("colors", [])
    patterns = params.get("patterns", [])

    # IMPORTANT: Extract colors from query if not explicitly provided
    if not colors and query:
        query_lower = query.lower()
        # Map German color names to English (for database)
        color_map = {
            "blau": "blue",
            "marine": "navy",
            "navy": "navy",
            "hellblau": "light blue",
            "dunkelblau": "dark blue",
            "grau": "grey",
            "schwarz": "black",
            "braun": "brown",
            "beige": "beige",
            "grün": "green",
        }

        extracted_colors = []
        for german, english in color_map.items():
            if german in query_lower:
                extracted_colors.append(english)

        if extracted_colors:
            colors = extracted_colors
            logger.info(f"[RAGTool] Extracted colors from query: {colors}")

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
            return ("""Hmm, ich habe gerade keine passenden Stoffe in der Datenbank gefunden.

Das kann daran liegen, dass die Datenbank noch nicht vollständig gefüllt ist.

**Was ich für dich tun kann:**
- Gib mir mehr Details zu deinen Wünschen (Farbe, Muster, Anlass)
- Oder lass uns direkt über Design und Schnitt sprechen

Wie möchtest du weitermachen? 🎩""", None)

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

        formatted = "**Passende Stoffe für deinen Anzug:**\n\n"
        for i, rec in enumerate(recommendations[:5], 1):
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

        if len(recommendations) > 5:
            formatted += f"_...und {len(recommendations) - 5} weitere Stoffe verfügbar_\n\n"

        # BUILD FABRIC IMAGES - Nuclear Option: Return images directly!
        fabric_images = []
        for i, rec in enumerate(recommendations[:2], 1):  # Top 2 fabrics
            fabric = rec.fabric

            # Get image URL - USE LOCAL IMAGES from storage/fabrics/images/
            # Flask serves these via /fabrics/images/ route
            fabric_code_clean = fabric.fabric_code.replace('/', '_')  # Clean filename
            image_url = f"/fabrics/images/{fabric_code_clean}.jpg"

            # Fallback: If database has external URLs, use those
            if fabric.image_urls and fabric.image_urls[0]:
                # Prefer local images, but keep external URLs as backup
                pass  # Keep local path

            # Ultimate fallback: placeholder (Flask route will handle FileNotFoundError)
            # No need for explicit check - Flask route redirects to placeholder if file missing

            fabric_images.append({
                "url": image_url,
                "fabric_code": fabric.fabric_code,
                "name": fabric.name or "Hochwertiger Stoff",
                "color": fabric.color or "Klassisch",
                "pattern": fabric.pattern or "Uni",
                "composition": fabric.composition or "Edle Wollmischung",
                "similarity_score": rec.similarity_score,
            })

        # TRACK FABRIC IMAGES IN SESSION HISTORY
        for img in fabric_images:
            session_state.shown_fabric_images.append({
                **img,  # Include all fabric data (url, fabric_code, name, etc.)
                "timestamp": datetime.now().isoformat(),
                "query": query,  # Track what user searched for
            })
        state["session_state"] = session_state

        logger.info(f"[RAGTool] Returning {len(fabric_images)} fabric images directly")
        logger.info(f"[RAGTool] Total fabric images in session: {len(session_state.shown_fabric_images)}")

        formatted += f"**Hier sind deine Top {len(fabric_images)} Stoffe mit Bildern! 🎨**"

        return formatted, fabric_images

    except Exception as e:
        logger.error(f"[RAGTool] Error during fabric search: {e}", exc_info=True)
        return ("""Entschuldigung, beim Abrufen der Stoffe gab es ein technisches Problem.

Lass uns trotzdem weitermachen – ich kann dir auch ohne Datenbank bei der Auswahl helfen!

Was ist dir wichtig bei deinem Anzug? 🎩""", None)

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
            fabrics=fabrics[:2],  # Top 2 fabrics
            occasion=occasion,
            style_keywords=style_keywords,
            session_id=session_id,
        )

        if response.success and response.image_url:
            logger.info(f"[DALLE_MoodBoard] Composite created: {response.image_url}")

            # Get fabric names for message
            fabric_names = [f.get("name", "Hochwertiger Stoff") for f in fabrics[:2]]

            message = f"""🎨 **Dein Mood Board ist fertig!**

Ich zeige dir die Top 2 Stoffe in ihrer perfekten Umgebung:
- **{fabric_names[0]}**
- **{fabric_names[1]}** (als Alternative)

Die kleinen Stoffbilder unten rechts zeigen die echten Referenzen! 📸

**Was denkst du?** Welcher Stoff gefällt dir besser? 🎩"""

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


async def _execute_dalle_outfit(
    params: Dict[str, Any], state: HenkGraphState
) -> tuple[str, Optional[str]]:
    """
    DALL-E Outfit Visualization Tool: Generiert fotorealistische Outfit-Darstellung.

    Args:
        params: Generation-Parameter (fabric_data, design_preferences, style_keywords, session_id)
        state: Graph State für Context

    Returns:
        Tuple of (formatted_message, image_url)
    """
    from tools.dalle_tool import get_dalle_tool

    fabric_data = params.get("fabric_data", {})
    design_preferences = params.get("design_preferences", {})
    style_keywords = params.get("style_keywords", [])
    session_id = params.get("session_id")

    # CHECK FOR FAVORITE FABRIC in session state
    session_state = state.get("session_state")
    favorite_fabric = None
    if session_state and session_state.favorite_fabric:
        favorite_fabric = session_state.favorite_fabric
        logger.info(f"[DALLE_Outfit] Using favorite fabric: {favorite_fabric['fabric_code']}")

        # Merge favorite fabric into fabric_data if not already present
        if not fabric_data or "fabric_code" not in fabric_data:
            fabric_data = {
                "fabric_code": favorite_fabric["fabric_code"],
                "name": favorite_fabric.get("name", ""),
                "color": favorite_fabric.get("color", ""),
                "pattern": favorite_fabric.get("pattern", ""),
                "composition": favorite_fabric.get("composition", ""),
                "image_url": favorite_fabric.get("image_url", ""),
            }
            logger.info("[DALLE_Outfit] Favorite fabric added to fabric_data")

    logger.info(
        f"[DALLE_Outfit] Generating outfit visualization: "
        f"fabrics={list(fabric_data.keys())}, design={list(design_preferences.keys())}"
    )

    try:
        dalle = get_dalle_tool()
        response = await dalle.generate_outfit_visualization(
            fabric_data=fabric_data,
            design_preferences=design_preferences,
            style_keywords=style_keywords,
            session_id=session_id,
        )

        if response.success and response.image_url:
            logger.info(f"[DALLE_Outfit] Success: {response.image_url}")

            # Build message with fabric info if favorite was used
            fabric_info = ""
            if favorite_fabric:
                fabric_info = f"\n🌟 **Mit deinem Favorit-Stoff:** {favorite_fabric['fabric_code']} - {favorite_fabric.get('name', '')}\n"

            message = f"""✨ **Dein Outfit-Entwurf ist fertig!**
{fabric_info}
So könnte dein maßgeschneiderter Anzug aussehen – basierend auf:
- Deiner Stoffauswahl ({fabric_data.get('fabric_code', 'N/A')})
- Den Design-Details (Revers, Schulter, etc.)
- Deinem persönlichen Stil

**Gefällt dir die Richtung?**

Wir können jederzeit Anpassungen vornehmen! 🎩"""

            return message, response.image_url

        else:
            logger.error(f"[DALLE_Outfit] Failed: {response.error}")
            message = """Entschuldigung, beim Erstellen des Outfit-Entwurfs gab es ein Problem.

Macht nichts – lass uns die Details besprechen und ich beschreibe dir dein Traumoutfit! 🎩"""
            return message, None

    except Exception as e:
        logger.error(f"[DALLE_Outfit] Exception: {e}", exc_info=True)
        message = """Entschuldigung, der Outfit-Entwurf konnte gerade nicht generiert werden.

Kein Problem – wir machen trotzdem weiter! Was möchtest du noch anpassen? 🎩"""
        return message, None


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

        # Get top 2 fabrics with images
        fabrics_with_images = []
        for fabric in fabrics[:10]:  # Check first 10 fabrics
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

            if len(fabrics_with_images) >= 2:
                break

        if not fabrics_with_images:
            logger.warning("[ShowFabricImages] No fabric images available")
            message = """Die Stoffbilder sind leider noch nicht verfügbar.

Aber ich kann dir die technischen Details zeigen – welcher Stoff interessiert dich am meisten? 🎩"""
            return message, None

        # Build message with fabric details
        occasion = params.get("occasion", "deinen Anlass")

        message = f"""🎨 **Hier sind deine Top {len(fabrics_with_images)} Stoff-Empfehlungen!**

"""

        for i, fabric in enumerate(fabrics_with_images, 1):
            message += f"""**{i}. {fabric['name']}** (Ref: {fabric['fabric_code']})
   🎨 Farbe: {fabric['color']}
   ✨ Muster: {fabric['pattern']}
   📦 Material: {fabric['composition']}

"""

        message += f"""Die Stoffe werden perfekt zu {occasion} passen!

**Was denkst du?** Welcher gefällt dir besser? 🎩"""

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


async def _execute_mark_favorite_fabric(params: Dict[str, Any], state: HenkGraphState) -> str:
    """
    Mark Favorite Fabric: User selects a favorite fabric from shown options.

    This fabric will be passed to DALL-E for outfit generation.

    Args:
        params: {
            "fabric_code": str,  # Which fabric to mark as favorite
            "selection_method": str,  # "index" (1st, 2nd) or "code" (10C4017)
        }
        state: Graph state with session_state

    Returns:
        Confirmation message
    """
    session_state = state.get("session_state")
    if not session_state:
        logger.error("[MarkFavorite] No session_state found")
        return "Fehler: Keine Session gefunden."

    fabric_code = params.get("fabric_code")
    selection_method = params.get("selection_method", "code")

    logger.info(f"[MarkFavorite] Marking favorite: fabric_code={fabric_code}, method={selection_method}")

    # If selection by index (e.g., "der erste", "nummer 2")
    if selection_method == "index":
        index = params.get("index", 0)
        shown_fabrics = session_state.shown_fabric_images

        if not shown_fabrics or index >= len(shown_fabrics):
            return f"Fehler: Kein Stoff an Position {index+1} gefunden."

        # Get fabric by index
        favorite = shown_fabrics[index]
        fabric_code = favorite["fabric_code"]
    else:
        # Find fabric by code in shown_fabric_images
        shown_fabrics = session_state.shown_fabric_images
        favorite = None

        for img in shown_fabrics:
            if img["fabric_code"] == fabric_code:
                favorite = img
                break

        if not favorite:
            return f"Fehler: Stoff {fabric_code} wurde nicht angezeigt."

    # Store favorite in session state
    session_state.favorite_fabric = {
        "fabric_code": favorite["fabric_code"],
        "name": favorite.get("name", ""),
        "color": favorite.get("color", ""),
        "pattern": favorite.get("pattern", ""),
        "composition": favorite.get("composition", ""),
        "image_url": favorite["url"],
        "marked_at": datetime.now().isoformat(),
    }

    state["session_state"] = session_state

    logger.info(f"[MarkFavorite] Favorite marked: {favorite['fabric_code']} - {favorite.get('name')}")

    return f"""**Perfekt! Dein Favorit ist gespeichert! 🌟**

**{favorite.get('name', 'Ausgewählter Stoff')}**
🏷️ Code: {favorite['fabric_code']}
🎨 Farbe: {favorite.get('color', 'Klassisch')}
✨ Muster: {favorite.get('pattern', 'Uni')}

Soll ich dir jetzt passende Outfit-Vorschläge mit diesem Stoff generieren? 🎨"""
