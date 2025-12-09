"""
Supervisor Agent: Intelligenter Workflow-Orchestrator

Der Supervisor ist das "Gehirn" des Routing-Systems. Er versteht User-Intent
und entscheidet flexibel, welcher Agent oder welches Tool als nächstes aktiviert wird.

Key Features:
- LLM-basierte Intent-Erkennung
- Context-aware Routing (berücksichtigt Phase, History, Customer-Daten)
- Flexible Sprünge (Rücksprung von H3 zu H1 möglich)
- Tool-Priorisierung (User sagt "zeig mir Stoffe" → sofort RAG Tool)
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any, List
import logging

from agents.prompt_loader import prompt_registry

logger = logging.getLogger(__name__)

try:  # Optional dependency: allow offline rule-based fallback in tests
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via offline path
    PydanticAgent = None


class SupervisorDecision(BaseModel):
    """
    Routing-Entscheidung des Supervisors.

    Attributes:
        next_destination: Wohin soll geroutet werden? (Agent/Tool/Clarification/End)
        reasoning: Begründung für diese Entscheidung (für Debugging/Logging)
        action_params: Optionale Parameter (z.B. Suchfilter für RAG Tool)
        user_message: Nachricht an User (nur bei clarification)
        confidence: Confidence Score 0.0-1.0 (wie sicher ist die Entscheidung?)
    """

    next_destination: Literal[
        "henk1",  # H1: Event-Klärung (Anlass, Budget, Timing)
        "design_henk",  # H2: Design-Phase (Schnitt, Stil, Farben)
        "laserhenk",  # H3: Messungen (Körpermaße erfassen)
        "rag_tool",  # Stoff-/Bild-Suche via RAG
        "comparison_tool",  # Vergleiche zwischen Optionen
        "pricing_tool",  # Preiskalkulation
        "clarification",  # User-Intent unklar → Rückfrage
        "end",  # Gespräch beenden
    ] = Field(description="Ziel-Agent oder -Tool für nächsten Schritt")

    reasoning: str = Field(
        description="Begründung für Routing-Entscheidung (1-2 Sätze)",
        min_length=10,
        max_length=200,
    )

    action_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameter für Aktion (z.B. {'fabric_type': 'wool', 'pattern': 'pinstripe'})",
    )

    user_message: Optional[str] = Field(
        default=None,
        description="Rückfrage an User (nur bei clarification)",
        max_length=500,
    )

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence Score: 0.0 (unsicher) bis 1.0 (sehr sicher)",
    )


class SupervisorAgent:
    """
    Intelligenter Supervisor für flexible Workflow-Orchestrierung.

    Der Supervisor nutzt ein LLM um User-Intent zu verstehen und zum
    optimalen Agent/Tool zu routen. Im Gegensatz zu rule-based routing
    kann er:
    - Natürliche Sprache verstehen
    - Context aus Conversation History nutzen
    - Flexibel zwischen Phasen springen
    - Tools on-demand aktivieren

    Usage:
        supervisor = SupervisorAgent()
        decision = await supervisor.decide_next_step(
            user_message="Zeig mir Wollstoffe",
            session_state={...},
            conversation_history=[...]
        )
        # decision.next_destination = "rag_tool"
        # decision.action_params = {"fabric_type": "wool"}
    """

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        """
        Initialisiert Supervisor mit LLM.

        Args:
            model: LLM Model String (default: gpt-4o-mini für Kosten-Effizienz)
                  gpt-4o-mini ist ausreichend für Routing-Entscheidungen
                  und deutlich günstiger als gpt-4
        """
        self.model = model

        if PydanticAgent is None:
            self.pydantic_agent = None
            logger.warning(
                "[SupervisorAgent] pydantic_ai not installed. Falling back to rule-based routing"
            )
        else:
            # Try both pydantic-ai API versions
            # v1.0+ doesn't accept result_type in constructor
            # v0.0.x requires result_type
            try:
                # Try new API first (v1.0+): No result_type parameter
                self.pydantic_agent = PydanticAgent(model, retries=2)
                logger.info(f"[SupervisorAgent] Initialized with model={model} (pydantic-ai v1.0+)")
            except Exception as e1:
                # New API failed, try old API (v0.0.x)
                try:
                    logger.debug(f"[SupervisorAgent] New API failed: {e1}, trying old API")
                    self.pydantic_agent = PydanticAgent(
                        model,
                        result_type=SupervisorDecision,
                        retries=2
                    )
                    logger.info(f"[SupervisorAgent] Initialized with model={model} (pydantic-ai v0.0.x)")
                except Exception as e2:
                    # Both APIs failed
                    self.pydantic_agent = None
                    logger.warning(
                        f"[SupervisorAgent] Failed to initialize PydanticAgent with both APIs. "
                        f"New API error: {e1}, Old API error: {e2}. "
                        "Falling back to rule-based routing"
                    )

    async def decide_next_step(
        self,
        user_message: str,
        session_state: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
    ) -> SupervisorDecision:
        """
        Trifft LLM-basierte Routing-Entscheidung.

        Analysiert User-Intent basierend auf:
        - Aktuellem User-Message
        - Session State (Phase, Customer-Daten, etc.)
        - Conversation History (für Context wie "von vorhin", "das letzte")

        Args:
            user_message: Aktuelle Nachricht vom User
            session_state: Session State mit customer_data, current_phase, etc.
            conversation_history: Liste der bisherigen Messages

        Returns:
            SupervisorDecision mit next_destination und reasoning

        Raises:
            Keine - Bei Fehler wird clarification Decision zurückgegeben

        Example:
            >>> decision = await supervisor.decide_next_step(
            ...     "Zeig mir Nadelstreifen",
            ...     {"current_phase": "H2", "customer_data": {...}},
            ...     [...]
            ... )
            >>> decision.next_destination
            'rag_tool'
            >>> decision.action_params
            {'pattern': 'pinstripe', 'query': 'Nadelstreifen'}
        """
        if self.pydantic_agent is None:
            logger.info("[SupervisorAgent] Using clarification fallback (no LLM available)")
            return SupervisorDecision(
                next_destination="clarification",
                reasoning="pydantic_ai not installed",
                user_message="Kannst du deine Anfrage noch einmal formulieren?",
                confidence=0.0,
            )

        system_prompt = self._build_supervisor_prompt(session_state)

        try:
            result = await self.pydantic_agent.run(
                user_message,
                message_history=self._format_history(conversation_history),
                deps={
                    "system_prompt": system_prompt,
                    "current_phase": session_state.get("current_phase", "H0"),
                    "customer_data": session_state.get("customer_data", {}),
                    "available_destinations": self._get_available_destinations(),
                },
            )

            # Handle both pydantic-ai API versions
            # Log result structure for debugging
            try:
                result_type = type(result).__name__
                result_attrs = [a for a in dir(result) if not a.startswith('_')][:15]
                logger.info(f"[SupervisorAgent] Result type: {result_type}")
                logger.info(f"[SupervisorAgent] Result attrs: {result_attrs}")
            except Exception as log_err:
                logger.warning(f"[SupervisorAgent] Failed to log result: {log_err}")

            # Extract decision from result
            decision = None

            if hasattr(result, 'data'):
                decision = result.data  # v0.0.x pattern
                logger.info("[SupervisorAgent] Using result.data (v0.0.x)")
            elif hasattr(result, 'output'):
                decision = result.output  # Common v1.0+ pattern
                logger.info("[SupervisorAgent] Using result.output (v1.0+)")
            elif isinstance(result, SupervisorDecision):
                decision = result  # Result IS the decision
                logger.info("[SupervisorAgent] Result is SupervisorDecision directly")
            else:
                # Try other common attribute names
                for attr_name in ['result', 'value', 'response', 'content']:
                    if hasattr(result, attr_name):
                        decision = getattr(result, attr_name)
                        logger.info(f"[SupervisorAgent] Using result.{attr_name}")
                        break

                if decision is None:
                    logger.error(f"[SupervisorAgent] Could not extract decision from result type {type(result)}")
                    raise ValueError(f"Unknown result structure: {type(result)}")

            # Validate we got a SupervisorDecision
            if not isinstance(decision, SupervisorDecision):
                logger.error(f"[SupervisorAgent] Decision is {type(decision).__name__}, not SupervisorDecision!")
                logger.error(f"[SupervisorAgent] Decision value: {decision}")
                raise TypeError(f"Expected SupervisorDecision, got {type(decision).__name__}")

            logger.info(
                f"[SupervisorAgent] Decision: {decision.next_destination} "
                f"(confidence={decision.confidence:.2f}) | "
                f"Reason: {decision.reasoning}"
            )

            return decision

        except Exception as e:
            logger.error(f"[SupervisorAgent] LLM call failed: {e}", exc_info=True)

            # Fallback: Clarification bei Fehler
            return SupervisorDecision(
                next_destination="clarification",
                reasoning="LLM error occurred, requesting clarification",
                user_message="Entschuldigung, ich hatte ein kurzes Problem. Kannst du das wiederholen?",
                confidence=0.0,
            )

    def _build_supervisor_prompt(self, session_state: Dict[str, Any]) -> str:
        """
        Baut context-aware System Prompt für Supervisor.

        Der Prompt enthält:
        - Aktuellen Phase-Context
        - Erfasste Customer-Daten
        - Verfügbare Destinations mit Beschreibung
        - Routing-Regeln

        Args:
            session_state: Session State für Context

        Returns:
            Vollständiger System Prompt
        """
        current_phase = session_state.get("current_phase", "H0")
        customer_data = session_state.get("customer_data", {})
        completeness = self._assess_completeness(customer_data)

        core_prompt = prompt_registry.get_prompt("core")

        dynamic_context = f"""Du bist der SUPERVISOR eines hochmodernen Bespoke-Schneider-Systems namens HENK.

**KONTEXT:**
Phase: {current_phase}
Erfasste Daten: {list(customer_data.keys()) if customer_data else "Keine"}
Datenvollständigkeit: {completeness}

**AUFGABE:**
Verstehe den User-Intent präzise und route zur optimalen Destination.

**DESTINATIONS:**

1. **henk1** (Event-Klärung H1)
   Nutze wenn: Anlass, Budget, Timing, Dresscode diskutiert wird
   Beispiele: "Ich brauche einen Anzug für Hochzeit", "Doch kein Smoking"

2. **design_henk** (Design-Phase H2)
   Nutze wenn: Schnitt, Stil, Farben, Design-Optionen besprochen werden
   Beispiele: "Ich will einen Zweireiher", "Was ist ein Peak Lapel?"

3. **laserhenk** (Messungen H3)
   Nutze wenn: Körpermaße erfasst oder besprochen werden
   Beispiele: "Wie messe ich meine Schulter?", "Maß scheint falsch"

4. **rag_tool** (Stoff-/Bild-Suche)
   Nutze wenn: Stoffe, Muster, Bilder angefordert werden
   Beispiele: "Zeig mir Wollstoffe", "Mehr Bilder von Nadelstreifen"
   WICHTIG: Auch nutzbar aus anderen Phasen! (sehr flexibel)
   action_params: {{"fabric_type": "...", "pattern": "...", "query": "..."}}

5. **comparison_tool** (Vergleiche)
   Nutze wenn: Optionen/Stoffe/Designs verglichen werden sollen
   Beispiele: "Was ist der Unterschied?", "Vergleich A und B"
   action_params: {{"items": ["id1", "id2"], "comparison_type": "..."}}

6. **pricing_tool** (Preiskalkulation)
   Nutze wenn: Preis, Kosten, Budget angefragt wird
   Beispiele: "Was kostet das?", "Passt ins Budget?"

7. **clarification** (Rückfrage)
   Nutze wenn: Intent unklar, zu vage, mehrdeutig
   Beispiele: "Hm", "Ok", "Interessant"
   MUSS user_message setzen mit gezielter Rückfrage!

8. **end** (Beenden)
   Nutze wenn: Kunde signalisiert Ende
   Beispiele: "Danke, das war's", "Bis dann"

**REGELN:**
✅ Rücksprünge erlaubt (H3 → H1 ist ok)
✅ Tools haben Priorität ("Zeig X" → Tool, egal welche Phase)
✅ Context nutzen (History für "von vorhin", "das letzte")
✅ Bei Zweifel → clarification
✅ action_params extrahieren aus User-Message

**QUALITÄT:**
- Ist next_destination logisch?
- Macht reasoning Sinn?
- Sind action_params vollständig?
- Ist confidence realistisch? (0.8-1.0=sicher, 0.5-0.8=unsicher, <0.5=sehr unsicher)

Antworte mit SupervisorDecision Objekt!"""

        return f"{core_prompt}\n\n---\n\n{dynamic_context}"

    def get_prompt_usage(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Expose prompt usage for debugging/tests."""
        return prompt_registry.get_usage_report()

    def _assess_completeness(self, customer_data: Dict[str, Any]) -> str:
        """
        Bewertet Vollständigkeit der Customer-Daten.

        Gibt qualitative Einschätzung basierend auf Anzahl erfasster Felder.
        Hilft dem Supervisor zu verstehen, wie viel bereits bekannt ist.

        Args:
            customer_data: Dictionary mit Customer-Daten

        Returns:
            String wie "Leer", "Minimal (2 Felder)", "Umfangreich (8 Felder)"
        """
        if not customer_data:
            return "Leer (0 Felder)"

        field_count = len(customer_data)

        if field_count < 3:
            return f"Minimal ({field_count} Felder)"
        elif field_count < 6:
            return f"Teilweise ({field_count} Felder)"
        else:
            return f"Umfangreich ({field_count} Felder)"

    def _get_available_destinations(self) -> List[str]:
        """
        Liefert Liste aller verfügbaren Destinations.

        In unserem Hybrid-Modell sind alle Destinations immer verfügbar,
        um maximale Flexibilität zu gewährleisten.

        Returns:
            Liste aller Destination-Strings
        """
        return [
            "henk1",
            "design_henk",
            "laserhenk",
            "rag_tool",
            "comparison_tool",
            "pricing_tool",
            "clarification",
            "end",
        ]

    def _format_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Formatiert Conversation History für PydanticAI.

        Konvertiert von unserem Message-Format zu PydanticAI's erwartetem Format.
        Nimmt nur die letzten 10 Messages um Token-Limit nicht zu sprengen.

        Args:
            history: Liste von Message-Dicts mit role, content, sender

        Returns:
            Liste von Dicts mit role und content (PydanticAI Format)
        """
        formatted = []

        for msg in history[-10:]:  # Nur letzte 10 Messages
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Nur user und assistant Messages (system Messages filtern)
            if role in ["user", "assistant"] and content:
                formatted.append({"role": role, "content": content})

        return formatted
