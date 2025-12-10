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
from typing import Dict, Any
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
            messages.append(
                {
                    "role": "assistant",
                    "content": decision.message or "Querying database for information...",
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
        messages.append(
            {
                "role": "assistant",
                "content": decision.message
                or "Konversation abgeschlossen. Nächster Schritt wird vorbereitet.",
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
            result = await _execute_rag_tool(action_params, state)

        elif next_agent == "comparison_tool":
            result = await _execute_comparison_tool(action_params, state)

        elif next_agent == "pricing_tool":
            result = await _execute_pricing_tool(action_params, state)

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


async def _execute_rag_tool(params: Dict[str, Any], state: HenkGraphState) -> str:
    """
    RAG Tool: Sucht Stoffe/Bilder via Vector Search.

    Args:
        params: Suchparameter (query, fabric_type, pattern)
        state: Graph State für Context

    Returns:
        Formatierte Suchergebnisse
    """
    from tools.rag_tool import RAGTool

    query = params.get("query", "")
    fabric_type = params.get("fabric_type")
    pattern = params.get("pattern")

    logger.info(
        f"[RAGTool] Searching: query='{query}', fabric_type={fabric_type}, pattern={pattern}"
    )

    rag = RAGTool()
    results = await rag.search(query, fabric_type=fabric_type, pattern=pattern)

    # Format Results
    if not results:
        return "Keine passenden Stoffe gefunden. Versuche andere Suchbegriffe."

    formatted = "**Passende Stoffe:**\n\n"
    for i, item in enumerate(results[:5], 1):
        formatted += f"**{i}. {item.get('name', 'Unbenannt')}**\n"
        formatted += f"   Material: {item.get('material', 'N/A')}\n"
        formatted += f"   Muster: {item.get('pattern', 'N/A')}\n"
        formatted += f"   Gewicht: {item.get('weight', 'N/A')}\n\n"

    if len(results) > 5:
        formatted += f"_...und {len(results) - 5} weitere Ergebnisse_"

    return formatted


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
