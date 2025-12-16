"""
Supervisor Agent: Intelligenter Workflow-Orchestrator

Der Supervisor ist der zentrale Router. Er entscheidet anhand von
User-Intent, SessionState und History, welches Ziel (Agent oder Tool)
als nächstes ausgeführt wird.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.agents.operator_phase_assessor import PhaseAssessment, PhaseAssessor
from agents.prompt_loader import prompt_registry
from models.customer import SessionState

logger = logging.getLogger(__name__)

try:  # Optional dependency: allow offline rule-based fallback in tests
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via offline path
    PydanticAgent = None


class SupervisorDecision(BaseModel):
    """Routing-Entscheidung des Supervisors."""

    next_destination: Literal[
        "henk1",  # H1: Event-Klärung (Anlass, Timing, Stoff-Farbe)
        "design_henk",  # H2: Design-Phase (Schnitt, Stil, Farben)
        "laserhenk",  # H3: Messungen (Körpermaße erfassen)
        "rag_tool",  # Stoff-/Bild-Suche via RAG
        "comparison_tool",  # Vergleiche zwischen Optionen
        "pricing_tool",  # Preiskalkulation
        "clarification",  # User-Intent unklar → Rückfrage
        "end",  # Gespräch beenden
    ] = Field(description="Ziel-Agent oder -Tool für nächsten Schritt")

    reasoning: str = Field(
        default="Routing based on user message analysis",
        description="Begründung für Routing-Entscheidung (1-2 Sätze)",
        min_length=10,
        max_length=500,
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
    """Intelligenter Supervisor für flexible Workflow-Orchestrierung."""

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        self.model = model
        self.phase_assessor = PhaseAssessor()

        if PydanticAgent is None:
            self.pydantic_agent = None
            logger.warning(
                "[SupervisorAgent] pydantic_ai not installed. Falling back to rule-based routing"
            )
        else:
            try:
                try:
                    self.pydantic_agent = PydanticAgent[SupervisorDecision](
                        model, retries=2
                    )
                    logger.info(
                        f"[SupervisorAgent] Initialized with model={model} (pydantic-ai v1.0+ Generic)"
                    )
                except (TypeError, AttributeError):
                    self.pydantic_agent = PydanticAgent(model, retries=2)
                    logger.info(
                        f"[SupervisorAgent] Initialized with model={model} (pydantic-ai v1.0+ plain)"
                    )
            except Exception as e1:
                try:
                    self.pydantic_agent = PydanticAgent(
                        model, result_type=SupervisorDecision, retries=2
                    )
                    logger.info(
                        f"[SupervisorAgent] Initialized with model={model} (pydantic-ai v0.0.x)"
                    )
                except Exception as e2:  # pragma: no cover - fallback path
                    self.pydantic_agent = None
                    logger.warning(
                        f"[SupervisorAgent] Failed to initialize PydanticAgent. "
                        f"New API error: {e1}, Old API error: {e2}. "
                        "Falling back to rule-based routing"
                    )

        if self.pydantic_agent is not None:
            @self.pydantic_agent.system_prompt
            async def get_system_prompt(ctx) -> str:
                deps = ctx.deps or {}
                system_prompt = deps.get("system_prompt", "")
                return system_prompt if system_prompt else self._get_default_system_prompt()

    async def decide_next_step(
        self,
        user_message: str,
        state: SessionState,
        conversation_history: List[Dict[str, Any]],
    ) -> SupervisorDecision:
        assessment = self.phase_assessor.assess(state)

        pre_routed = self._pre_route(user_message, state)
        if pre_routed:
            logger.info(
                "[SupervisorAgent] Pre-routing to %s (confidence=%.2f)",
                pre_routed.next_destination,
                pre_routed.confidence,
            )
            return pre_routed

        if self.pydantic_agent is None:
            logger.info("[SupervisorAgent] Using clarification fallback (no LLM available)")
            return SupervisorDecision(
                next_destination="clarification",
                reasoning="pydantic_ai not installed",
                user_message="Kannst du deine Anfrage noch einmal formulieren?",
                confidence=0.0,
            )

        system_prompt = self._build_supervisor_prompt(state, assessment)

        try:
            try:
                result = await self.pydantic_agent.run(
                    user_message,
                    result_type=SupervisorDecision,
                    message_history=self._format_history(conversation_history),
                    deps={
                        "system_prompt": system_prompt,
                        "current_phase": getattr(state, "current_agent", None) or "H0",
                        "customer_data": state.customer.model_dump(),
                        "available_destinations": self._get_available_destinations(),
                    },
                )
            except TypeError:
                result = await self.pydantic_agent.run(
                    user_message,
                    message_history=self._format_history(conversation_history),
                    deps={
                        "system_prompt": system_prompt,
                        "current_phase": getattr(state, "current_agent", None) or "H0",
                        "customer_data": state.customer.model_dump(),
                        "available_destinations": self._get_available_destinations(),
                    },
                )

            decision: Optional[SupervisorDecision] = None
            if hasattr(result, "data"):
                decision = result.data
            elif hasattr(result, "output"):
                decision = result.output
            elif isinstance(result, SupervisorDecision):
                decision = result

            if decision is None:
                for attr_name in ["result", "value", "response", "content"]:
                    if hasattr(result, attr_name):
                        candidate = getattr(result, attr_name)
                        if isinstance(candidate, SupervisorDecision):
                            decision = candidate
                            break
                        if isinstance(candidate, dict):
                            decision = SupervisorDecision(**candidate)
                            break
                        if isinstance(candidate, str):
                            import json

                            decision = SupervisorDecision(**json.loads(candidate))
                            break

            if decision is None:
                raise ValueError(f"Unknown result structure: {type(result)}")

            decision = self._apply_hard_gates(decision, assessment)

            logger.info(
                "[SupervisorAgent] Decision: %s (confidence=%.2f) | Reason: %s",
                decision.next_destination,
                decision.confidence,
                decision.reasoning,
            )

            return decision

        except Exception as e:  # pragma: no cover - safety
            logger.error(f"[SupervisorAgent] LLM call failed: {e}", exc_info=True)

            if isinstance(e, TypeError) and "Expected SupervisorDecision" in str(e):
                logger.warning(
                    "[SupervisorAgent] Structured output not working, using rule-based routing"
                )
                return self._rule_based_routing(user_message, state, conversation_history)

            return SupervisorDecision(
                next_destination="clarification",
                reasoning="LLM error occurred, requesting clarification",
                user_message="Entschuldigung, ich hatte ein kurzes Problem. Kannst du das wiederholen?",
                confidence=0.0,
            )

    def _pre_route(self, user_message: str, state: SessionState) -> Optional[SupervisorDecision]:
        """Rule-based fast path for obvious tool intents."""

        text = (user_message or "").lower()
        if not text:
            return None

        color_hint = None
        if state.design_preferences.preferred_colors:
            color_hint = ", ".join(state.design_preferences.preferred_colors)

        fabric_keywords = [
            "stoff",
            "stoffe",
            "fabric",
            "muster",
            "farbe",
            "farben",
            "bild",
            "bilder",
            "foto",
        ]
        pricing_keywords = ["preis", "kosten", "teuer", "günstig"]
        comparison_keywords = ["vergleich", "unterschied", "vs", "gegenüber"]
        measurement_keywords = ["maß", "messen", "messung", "größen", "size"]

        def _matches(keywords: list[str]) -> bool:
            return any(keyword in text for keyword in keywords)

        if _matches(fabric_keywords):
            return SupervisorDecision(
                next_destination="rag_tool",
                reasoning="Detected fabric/image intent via keywords",
                action_params={"query": user_message, "color": color_hint},
                confidence=0.92,
            )

        if _matches(pricing_keywords):
            return SupervisorDecision(
                next_destination="pricing_tool",
                reasoning="Detected pricing intent via keywords",
                action_params={"query": user_message},
                confidence=0.9,
            )

        if _matches(comparison_keywords):
            return SupervisorDecision(
                next_destination="comparison_tool",
                reasoning="Detected comparison intent via keywords",
                action_params={"query": user_message},
                confidence=0.9,
            )

        if _matches(measurement_keywords):
            return SupervisorDecision(
                next_destination="laserhenk",
                reasoning="Detected measurement intent via keywords",
                confidence=0.88,
            )

        return None

    def _build_supervisor_prompt(
        self, session_state: SessionState, assessment: PhaseAssessment
    ) -> str:
        current_phase = getattr(session_state, "current_agent", None) or "H0"
        customer_data = session_state.customer.model_dump()
        completeness = self._assess_completeness(customer_data)

        dynamic_context = f"Current phase: {current_phase}\n"
        dynamic_context += f"Customer completeness: {completeness}\n"
        dynamic_context += f"Missing fields: {', '.join(assessment.missing_fields) or 'keine'}\n"
        dynamic_context += f"Recommended phase: {assessment.recommended_phase}\n"

        optional_fields = [f"{k}={v}" for k, v in customer_data.items() if v]
        optional_context = " | ".join(optional_fields) or "keine"  # avoid empty string
        dynamic_context += f"Known customer data: {optional_context}"

        core_prompt = self._get_default_system_prompt()
        return f"{core_prompt}\n\n---\n\n{dynamic_context}"

    def get_prompt_usage(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Expose prompt usage for debugging/tests."""
        return prompt_registry.get_usage_report()

    def _assess_completeness(self, customer_data: Dict[str, Any]) -> str:
        if not customer_data:
            return "Leer (0 Felder)"

        field_count = len(customer_data)

        if field_count < 3:
            return f"Minimal ({field_count} Felder)"
        elif field_count < 6:
            return f"Teilweise ({field_count} Felder)"
        else:
            return f"Umfangreich ({field_count} Felder)"

    def _get_default_system_prompt(self) -> str:
        return """You are a routing supervisor for a bespoke suit consultation system.

Your task is to analyze the user's message and decide which agent or tool should handle it next.

Return a SupervisorDecision object with:
- next_destination: The agent/tool to route to
- reasoning: Brief explanation (1-2 sentences)
- action_params: Optional parameters for the destination
- confidence: 0.0-1.0 (how confident you are)

Available destinations:
- henk1: Initial consultation (occasion, timing, fabric color)
- design_henk: Design preferences (cut, style, colors)
- laserhenk: Measurements
- rag_tool: Fabric/image search
- comparison_tool: Compare options
- pricing_tool: Price calculation
- clarification: User intent unclear
- end: End conversation

RULES:
✅ HENK1 must have occasion + timing + fabric color before design_henk
✅ Tools can be triggered from any phase if user explicitly asks
✅ Use clarification only when intent is unclear
✅ Be concise in reasoning

IMPORTANT: Always return a valid SupervisorDecision object with all required fields."""

    def _rule_based_routing(
        self,
        user_message: str,
        session_state: SessionState,
        conversation_history: List[Dict[str, Any]],
    ) -> SupervisorDecision:
        _ = user_message, conversation_history  # unused
        assessment = self.phase_assessor.assess(session_state)

        if not assessment.is_henk1_complete:
            return SupervisorDecision(
                next_destination="henk1",
                reasoning="Rule-based routing to complete HENK1 essentials",
                confidence=0.65,
            )

        if not assessment.is_design_complete:
            return SupervisorDecision(
                next_destination="design_henk",
                reasoning="Rule-based routing to complete design fields",
                confidence=0.65,
            )

        if not assessment.is_measurements_complete:
            return SupervisorDecision(
                next_destination="laserhenk",
                reasoning="Rule-based routing to capture measurements",
                confidence=0.65,
            )

        return SupervisorDecision(
            next_destination="end",
            reasoning="All phases complete, ending session",
            confidence=0.8,
        )

    def _apply_hard_gates(
        self, decision: SupervisorDecision, assessment: PhaseAssessment
    ) -> SupervisorDecision:
        if decision.next_destination == "design_henk" and not assessment.is_henk1_complete:
            decision.next_destination = "henk1"
            decision.reasoning += " | HENK1 essentials incomplete, rerouting"

        return decision

    def _format_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in history[-20:]:
            role = msg.get("role") or msg.get("type")
            content = msg.get("content") or ""
            if role and content:
                formatted.append({"role": role, "content": content})
        return formatted
