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

from typing import Dict, Any
import logging

from agents.supervisor_agent import SupervisorAgent
from agents.henk1 import Henk1Agent
from agents.design_henk import DesignHenkAgent
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
            logger.info(f"[Singleton] Henk1Agent created")
        elif agent_name == "design_henk":
            _agent_instances[agent_name] = DesignHenkAgent()
            logger.info(f"[Singleton] DesignHenkAgent created")
        # TODO: Weitere Agents hier hinzufügen
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

    # Basis-Check: Minimale Länge
    if not user_input or len(user_input.strip()) < 3:
        state["is_valid"] = False
        state["messages"].append({
            "role": "system",
            "content": "Eingabe zu kurz. Bitte mindestens 3 Zeichen eingeben.",
            "sender": "validator",
            "timestamp": None
        })
        logger.warning(f"[Validator] Rejected: '{user_input}' (too short)")
        return state

    # TODO: Weitere Validierungen
    # - Profanity Filter
    # - Spam Detection
    # - Rate Limiting (via session_id)

    state["is_valid"] = True
    logger.info(f"[Validator] Approved: '{user_input[:50]}...'")

    return state


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

    logger.info(f"[SmartOperator] Analyzing: '{user_input[:60]}...'")

    # Supervisor trifft Entscheidung
    supervisor = get_supervisor()
    decision = await supervisor.decide_next_step(
        user_input,
        session_state,
        conversation_history
    )

    # Update State basierend auf Decision
    state["next_agent"] = decision.next_destination
    state["current_agent"] = decision.next_destination
    state["pending_action"] = decision.action_params
    state["metadata"]["supervisor_reasoning"] = decision.reasoning
    state["metadata"]["confidence"] = decision.confidence

    # Bei clarification: Sofort Rückfrage an User
    if decision.next_destination == "clarification" and decision.user_message:
        state["messages"].append({
            "role": "assistant",
            "content": decision.user_message,
            "sender": "supervisor",
            "metadata": {
                "reasoning": decision.reasoning,
                "confidence": decision.confidence
            }
        })
        state["awaiting_user_input"] = True

    logger.info(
        f"[SmartOperator] Routed to '{decision.next_destination}' "
        f"(confidence={decision.confidence:.2f})"
    )

    return state


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

    logger.info(f"[Conversation] Processing with agent='{current_agent_name}'")

    # Hol Agent
    agent = get_agent(current_agent_name)

    if not agent:
        logger.error(f"[Conversation] Unknown agent: {current_agent_name}")
        state["next_agent"] = "clarification"
        state["messages"].append({
            "role": "system",
            "content": "Interner Fehler: Agent nicht gefunden.",
            "sender": "system"
        })
        return state

    # Entscheide: LLM oder Rule-based?
    input_data = {"user_input": user_input}

    try:
        if agent.needs_llm(session_state, input_data):
            logger.info(f"[Conversation] Using LLM for {current_agent_name}")
            decision = await agent.process_with_llm(session_state, user_input)
        else:
            logger.info(f"[Conversation] Using rules for {current_agent_name}")
            decision = await agent.process(session_state, input_data)

        # Update State mit Agent-Decision
        state["next_agent"] = decision.next_agent
        state["pending_action"] = decision.action
        state["awaiting_user_input"] = decision.awaiting_input
        state["phase_complete"] = decision.phase_complete

        # Append Agent-Response zu Messages
        state["messages"].append({
            "role": "assistant",
            "content": decision.response_text,
            "sender": current_agent_name,
            "metadata": decision.metadata
        })

        logger.info(
            f"[Conversation] Decision: next_agent='{decision.next_agent}', "
            f"phase_complete={decision.phase_complete}"
        )

    except Exception as e:
        logger.error(f"[Conversation] Agent failed: {e}", exc_info=True)

        # Fallback bei Fehler
        state["next_agent"] = "clarification"
        state["messages"].append({
            "role": "assistant",
            "content": "Entschuldigung, ich hatte ein Problem. Kannst du das nochmal sagen?",
            "sender": current_agent_name
        })
        state["awaiting_user_input"] = True

    return state


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

    logger.info(f"[ToolsDispatcher] Executing tool='{next_agent}' with params={action_params}")

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

        # Append Result zu Messages
        state["messages"].append({
            "role": "assistant",
            "content": result,
            "sender": next_agent
        })

        logger.info(f"[ToolsDispatcher] Tool '{next_agent}' executed successfully")

    except Exception as e:
        logger.error(f"[ToolsDispatcher] Tool failed: {e}", exc_info=True)

        state["messages"].append({
            "role": "assistant",
            "content": f"Entschuldigung, das Tool '{next_agent}' hatte ein Problem.",
            "sender": next_agent
        })

    state["awaiting_user_input"] = True
    return state


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

    logger.info(f"[RAGTool] Searching: query='{query}', fabric_type={fabric_type}, pattern={pattern}")

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


async def _execute_comparison_tool(params: Dict[str, Any], state: HenkGraphState) -> str:
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

    logger.info(f"[ComparisonTool] Comparing {len(items)} items of type '{comparison_type}'")

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
    garment_type = params.get("garment_type") or customer_data.get("garment_type", "suit")

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
            "suit": 1800,        # 2-Teiler
            "three_piece": 2100, # 3-Teiler
            "jacket": 1200,      # Sakko einzeln
            "trousers": 600,     # Hose einzeln
            "vest": 400,         # Weste einzeln
            "coat": 2500,        # Mantel
            "tuxedo": 2200,      # Smoking
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
