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
        min_length=5,
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
                self.pydantic_agent = PydanticAgent[SupervisorDecision](model, retries=2)
                logger.info(
                    f"[SupervisorAgent] Initialized with model={model} (pydantic-ai generic)"
                )
            except Exception:
                try:
                    self.pydantic_agent = PydanticAgent(
                        model, result_type=SupervisorDecision, retries=2
                    )
                    logger.info(
                        f"[SupervisorAgent] Initialized with model={model} (pydantic-ai legacy)"
                    )
                except Exception:
                    self.pydantic_agent = None
                    logger.warning(
                        "[SupervisorAgent] Failed to initialize PydanticAgent. Using rule-based routing"
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
            decision = self._offline_route(user_message, state, assessment)
            return self._apply_hard_gates(decision, assessment)

        system_prompt = self._build_supervisor_prompt(state, assessment)

        try:
            run_kwargs = {
                "message_history": self._format_history(conversation_history),
                "deps": {
                    "system_prompt": system_prompt,
                    "current_phase": getattr(state, "current_agent", None) or "H0",
                    "customer_data": state.customer.model_dump(),
                    "available_destinations": self._get_available_destinations(),
                },
            }

            try:
                result = await self.pydantic_agent.run(
                    user_message, result_type=SupervisorDecision, **run_kwargs
                )
            except TypeError:
                result = await self.pydantic_agent.run(user_message, **run_kwargs)

            decision = self._extract_decision(result)
            decision = self._apply_hard_gates(decision, assessment)

            logger.info(
                "[SupervisorAgent] Decision: %s (confidence=%.2f) | Reason: %s",
                decision.next_destination,
                decision.confidence,
                decision.reasoning,
            )

            return decision

        except Exception as exc:  # pragma: no cover - safety fallback
            logger.error(f"[SupervisorAgent] LLM call failed: {exc}", exc_info=True)
            decision = self._offline_route(user_message, state, assessment)
            return self._apply_hard_gates(decision, assessment)

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

        dynamic_context = f"Current phase: {current_phase}\n"
        dynamic_context += (
            f"Missing fields: {', '.join(assessment.missing_fields) or 'keine'}\n"
        )
        dynamic_context += f"Recommended phase: {assessment.recommended_phase}\n"

        optional_fields = [f"{k}={v}" for k, v in customer_data.items() if v]
        optional_context = " | ".join(optional_fields) or "keine"  # avoid empty string
        dynamic_context += f"Known customer data: {optional_context}"

        core_prompt = self._get_default_system_prompt()
        return f"{core_prompt}\n\n---\n\n{dynamic_context}"

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

    def _offline_route(
        self, user_message: str, state: SessionState, assessment: PhaseAssessment
    ) -> SupervisorDecision:
        pre_routed = self._pre_route(user_message, state)
        if pre_routed:
            return pre_routed

        if not assessment.is_henk1_complete:
            return SupervisorDecision(
                next_destination="henk1",
                reasoning="Offline routing: HENK1 essentials incomplete",
                confidence=0.65,
            )

        if not assessment.is_design_complete:
            return SupervisorDecision(
                next_destination="design_henk",
                reasoning="Offline routing: design details missing",
                confidence=0.65,
            )

        if not assessment.is_measurements_complete:
            return SupervisorDecision(
                next_destination="laserhenk",
                reasoning="Offline routing: measurements missing",
                confidence=0.65,
            )

        return SupervisorDecision(
            next_destination="end",
            reasoning="Offline routing: all phases complete",
            confidence=0.6,
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

    def _extract_decision(self, result: Any) -> SupervisorDecision:
        if isinstance(result, SupervisorDecision):
            return result

        for attr_name in ["data", "output", "result", "value", "response", "content"]:
            candidate = getattr(result, attr_name, None)
            if isinstance(candidate, SupervisorDecision):
                return candidate
            if isinstance(candidate, dict):
                return SupervisorDecision(**candidate)
            if isinstance(candidate, str):
                import json

                return SupervisorDecision(**json.loads(candidate))

        raise ValueError(f"Unknown result structure: {type(result)}")

    def _get_available_destinations(self) -> list[str]:
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

    def offline_route(
        self, user_message: str, state: SessionState, assessment: PhaseAssessment | None = None
    ) -> SupervisorDecision:
        """Public offline routing helper for nodes without LLM access."""

        active_assessment = assessment or self.phase_assessor.assess(state)
        decision = self._offline_route(user_message, state, active_assessment)
        return self._apply_hard_gates(decision, active_assessment)

    def get_prompt_usage(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Expose prompt usage for debugging/tests."""
        return prompt_registry.get_usage_report()
