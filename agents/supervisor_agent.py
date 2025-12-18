"""Supervisor agent responsible for all routing decisions."""
from __future__ import annotations

import inspect
import json
import logging
import os
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.agents.operator_phase_assessor import PhaseAssessment, PhaseAssessor
from models.customer import SessionState

logger = logging.getLogger(__name__)

try:  # Optional dependency: allow offline rule-based fallback
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via offline path
    PydanticAgent = None


class SupervisorDecision(BaseModel):
    """Structured routing decision returned by the supervisor."""

    next_destination: Literal[
        "henk1",
        "design_henk",
        "laserhenk",
        "rag_tool",
        "comparison_tool",
        "pricing_tool",
        "clarification",
        "end",
    ] = Field(description="Agent or tool to handle the next step")

    reasoning: str = Field(
        default="Routing based on user message analysis",
        description="Brief reasoning for the routing decision",
        min_length=5,
        max_length=500,
    )

    action_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for the routed tool/agent",
    )

    user_message: Optional[str] = Field(
        default=None,
        description="Message to present to the user (clarification/end)",
        max_length=500,
    )

    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )


class SupervisorAgent:
    """Central router that decides the next destination."""

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        self.model = model
        self.phase_assessor = PhaseAssessor()
        self._last_extract_path: str = "unknown"

        self.pydantic_agent = None
        if PydanticAgent is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                self.pydantic_agent = PydanticAgent[SupervisorDecision](model, retries=2)
            except Exception:
                try:
                    self.pydantic_agent = PydanticAgent(
                        model, result_type=SupervisorDecision, retries=2
                    )
                except Exception:
                    self.pydantic_agent = None
                    logger.warning(
                        "[SupervisorAgent] Failed to initialize PydanticAgent. Using offline routing.",
                    )
        elif PydanticAgent is None:
            logger.warning(
                "[SupervisorAgent] pydantic_ai not installed. Falling back to rule-based routing",
            )

        if self.pydantic_agent is not None:
            @self.pydantic_agent.system_prompt
            async def get_system_prompt(ctx) -> str:
                deps = ctx.deps or {}
                return deps.get("system_prompt") or ""

    async def decide_next_step(
        self,
        user_message: str,
        state: SessionState,
        conversation_history: List[dict],
    ) -> SupervisorDecision:
        assessment = self.phase_assessor.assess(state)

        pre_routed = self._pre_route(user_message, state)
        if pre_routed:
            return self._apply_hard_gates(pre_routed, assessment)

        if self.pydantic_agent is None:
            decision = self._offline_route(user_message, state, assessment)
            return self._apply_hard_gates(decision, assessment)

        system_prompt = self._build_supervisor_prompt(state, assessment)

        try:
            base_kwargs = {
                "message_history": self._format_history(conversation_history),
                "deps": {"system_prompt": system_prompt},
            }
            run_sig = inspect.signature(self.pydantic_agent.run)
            allowed_params = set(run_sig.parameters.keys())

            run_kwargs = {
                key: value for key, value in base_kwargs.items() if key in allowed_params
            }

            if "response_format" in allowed_params:
                run_kwargs["response_format"] = {"type": "json_object"}

            use_result_type = "result_type" in allowed_params

            async def _call_agent(kwargs: dict, with_result_type: bool):
                if with_result_type:
                    return await self.pydantic_agent.run(
                        user_message, result_type=SupervisorDecision, **kwargs
                    )
                return await self.pydantic_agent.run(user_message, **kwargs)

            try:
                result = await _call_agent(run_kwargs, use_result_type)
            except TypeError as exc:
                logger.warning(
                    "[SupervisorAgent] agent.run rejected kwargs (%s); retrying minimal",
                    exc,
                )
                minimal_kwargs = {
                    key: value
                    for key, value in run_kwargs.items()
                    if key in {"deps", "message_history"}
                }
                try:
                    result = await _call_agent(minimal_kwargs, False)
                except Exception as exc2:
                    logger.error(
                        "[SupervisorAgent] agent.run failed after retry: %s",
                        exc2,
                        exc_info=True,
                    )
                    return self._fallback_decision(
                        "Supervisor LLM call failed after retry"
                    )

            try:
                decision = self._extract_decision(result)
            except (ValueError, json.JSONDecodeError) as exc:
                logger.error(
                    "[SupervisorAgent] Decision parsing failed, falling back: %s",
                    exc,
                    exc_info=True,
                )
                decision = self._fallback_decision(
                    "LLM decision parse failure, safe fallback"
                )
        except Exception as exc:  # pragma: no cover - safety fallback
            logger.error(f"[SupervisorAgent] LLM routing failed: {exc}", exc_info=True)
            decision = self._fallback_decision(
                "Unexpected supervisor exception, safe fallback"
            )

        decision = self._apply_hard_gates(decision, assessment)

        logger.info(
            "[SupervisorAgent] Decision: %s | confidence=%.2f | reason=%s | extract_path=%s",
            decision.next_destination,
            decision.confidence,
            decision.reasoning,
            self._last_extract_path,
        )

        return decision

    def _pre_route(self, user_message: str, state: SessionState) -> Optional[SupervisorDecision]:
        text = (user_message or "").lower()
        if not text:
            return None

        # STATE-BASED ROUTING: Execute queued RAG if HENK1 prepared it
        if state.henk1_rag_queried and not state.henk1_fabrics_shown:
            # HENK1 has set rag_queried flag but fabrics haven't been shown yet
            # This means RAG needs to be executed now!
            query = user_message  # Use current user message as query

            # If rag_context already exists (from previous RAG execution), use that query
            if hasattr(state, 'rag_context') and state.rag_context and isinstance(state.rag_context, dict):
                query = state.rag_context.get("query", user_message)

            logger.info("[SupervisorAgent] ✅ State-based RAG trigger detected (henk1_rag_queried=True, fabrics_shown=False)")
            return SupervisorDecision(
                next_destination="rag_tool",
                reasoning="Executing queued RAG request from HENK1 (state-based trigger)",
                action_params={"query": query},
                confidence=0.98,
            )

        selection_keywords = [
            "rechtes foto", "linkes foto", "rechts", "links",
            "zweite", "erste", "foto",
            "nummer", "nr.", "nr ", "no.", "number",
            "den ersten", "den zweiten", "die erste", "die zweite",
            "stoff 1", "stoff 2", "#1", "#2",
            "ein passt", "eins", "zwei"  # "wenn die nr. ein passt"
        ]

        design_keywords = [
            "revers",
            "stegrevers",
            "spitzrevers",
            "schalkragen",
            "schulter",
            "polster",
            "bundfalte",
            "futter",
        ]

        # DEBUG: Log fabric selection check
        logger.info(f"[SupervisorAgent] Checking fabric selection: text='{text}', shown_fabric_images={len(state.shown_fabric_images) if state.shown_fabric_images else 0}")

        if state.shown_fabric_images and any(keyword in text for keyword in selection_keywords):
            logger.info(f"[SupervisorAgent] ✅ Fabric selection detected: '{text}' matches keywords, routing to HENK1")
            return SupervisorDecision(
                next_destination="henk1",
                reasoning="Detected fabric selection, routing back to henk1/design flow",
                user_message=user_message,
                confidence=0.95,
            )
        else:
            if state.shown_fabric_images:
                logger.info(f"[SupervisorAgent] ❌ No fabric selection keyword found in '{text}'")
            else:
                logger.info(f"[SupervisorAgent] ❌ No shown_fabric_images in state (empty or None)")

        design_phase_active = bool(
            state.favorite_fabric
            or state.henk1_to_design_payload
            or state.henk1_fabrics_shown
            or state.design_preferences.revers_type
        )

        if design_phase_active and any(keyword in text for keyword in design_keywords):
            logger.info(
                "[SupervisorAgent] ✅ Design preference detected: '%s' matches design keywords, routing to DESIGN_HENK",
                text,
            )
            return SupervisorDecision(
                next_destination="design_henk",
                reasoning="Detected design preference update during design phase",
                user_message=user_message,
                confidence=0.93,
            )

        color_hint = None
        if state.design_preferences.preferred_colors:
            color_hint = ", ".join(state.design_preferences.preferred_colors)
        elif state.design_preferences.lining_color:
            color_hint = state.design_preferences.lining_color

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
            "image",
            "picture",
        ]
        pricing_keywords = ["preis", "kosten", "teuer", "günstig", "price", "cost"]
        comparison_keywords = ["vergleich", "unterschied", "vs", "gegenüber", "compare"]
        measurement_keywords = ["maß", "messen", "messung", "größen", "size", "measurement"]

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

    def _fallback_decision(self, reason: str) -> SupervisorDecision:
        """Return a safe routing decision back to HENK1 without raising."""

        self._last_extract_path = "fallback"
        return SupervisorDecision(
            next_destination="henk1",
            reasoning=reason,
            user_message="Sag mir kurz Anlass, Timing und Farbrichtung – dann zeige ich Stoffe.",
            confidence=0.5,
        )

    def _build_supervisor_prompt(self, state: SessionState, assessment: PhaseAssessment) -> str:
        customer_data = state.customer.model_dump()
        dynamic_context = [
            "⚠️ CRITICAL: You MUST return ONLY valid JSON. NO explanatory text before or after the JSON object.",
            "",
            "REQUIRED JSON STRUCTURE:",
            "{",
            '  "next_destination": "henk1",  // MUST be ONE OF: henk1, design_henk, rag_tool, pricing_tool, comparison_tool, laserhenk, clarification, end',
            '  "reasoning": "Brief explanation of routing decision",',
            '  "confidence": 0.9  // Float between 0.0 and 1.0',
            "}",
            "",
            "IMPORTANT: next_destination must be a SINGLE value, not multiple values separated by |",
            "",
            "Du bist der Supervisor. Entscheide den nächsten Schritt (Agent oder Tool).",
            "HENK1 Essentials: Anlass, Timing (event_date auch weich) und Stoff-Farbe sind Pflicht. Budget ist optional.",
            f"Missing fields laut Assessment: {', '.join(assessment.missing_fields) or 'keine'}",
            f"Recommended phase: {assessment.recommended_phase}",
            "Tools (rag/pricing/comparison/measurement) dürfen jederzeit, wenn die Intention klar ist.",
            "Wenn Intention unklar ist → clarification. End nur wenn wirklich fertig.",
        ]

        optional_fields = [f"{k}={v}" for k, v in customer_data.items() if v]
        if optional_fields:
            dynamic_context.append(f"Customer data: {' | '.join(optional_fields)}")

        return "\n".join(dynamic_context)

    def _offline_route(
        self, user_message: str, state: SessionState, assessment: PhaseAssessment
    ) -> SupervisorDecision:
        pre_routed = self._pre_route(user_message, state)
        if pre_routed:
            return pre_routed

        if assessment.recommended_phase == "henk1":
            reason = "Offline routing: HENK1 essentials missing"
        elif assessment.recommended_phase == "design_henk":
            reason = "Offline routing: design details incomplete"
        elif assessment.recommended_phase == "laserhenk":
            reason = "Offline routing: measurements incomplete"
        else:
            reason = "Offline routing: all phases complete"

        return SupervisorDecision(
            next_destination=assessment.recommended_phase,
            reasoning=reason,
            confidence=0.65,
        )

    def _apply_hard_gates(
        self, decision: SupervisorDecision, assessment: PhaseAssessment
    ) -> SupervisorDecision:
        if decision.next_destination == "design_henk" and not assessment.is_henk1_complete:
            decision.next_destination = "henk1"
            decision.reasoning = (
                f"{decision.reasoning} | HENK1 essentials incomplete, rerouting to henk1"
            )
        return decision

    def _format_history(self, history: List[dict]) -> List[dict]:
        formatted: List[dict] = []
        for msg in history[-20:]:
            role = msg.get("role") or msg.get("type")
            content = msg.get("content") or ""
            if role and content:
                formatted.append({"role": role, "content": content})
        return formatted

    def _extract_decision(self, result: Any) -> SupervisorDecision:
        def _build_decision(payload: dict, source: str) -> SupervisorDecision:
            self._last_extract_path = source
            logger.debug("[SupervisorAgent] extract_decision: %s", source)
            return SupervisorDecision(**payload)

        # 1) Already a SupervisorDecision
        if isinstance(result, SupervisorDecision):
            self._last_extract_path = "direct"
            logger.debug("[SupervisorAgent] extract_decision: direct SupervisorDecision")
            return result

        # 2) Prefer explicit output container
        output_candidate = getattr(result, "output", None)
        if isinstance(output_candidate, SupervisorDecision):
            return _build_decision(output_candidate.model_dump(), "output")
        if isinstance(output_candidate, dict):
            return _build_decision(output_candidate, "output")

        # 3) Fallback to data container
        data_candidate = getattr(result, "data", None)
        if isinstance(data_candidate, SupervisorDecision):
            return _build_decision(data_candidate.model_dump(), "data")
        if isinstance(data_candidate, dict):
            return _build_decision(data_candidate, "data")

        # 4) Final string-based parsing
        candidate = getattr(result, "output", None) or getattr(result, "data", None)
        if candidate is None:
            candidate = getattr(result, "result", None) or getattr(result, "value", None)
        if candidate is None:
            candidate = getattr(result, "response", None) or getattr(result, "content", None)

        if isinstance(candidate, SupervisorDecision):
            return _build_decision(candidate.model_dump(), "string_container_decision")

        if isinstance(candidate, dict):
            return _build_decision(candidate, "string_container_dict")

        if isinstance(candidate, str):
            raw = str(candidate)
            raw = raw.strip()
            logger.debug(
                "[SupervisorAgent] Raw decision len=%s preview=%s",
                len(raw),
                raw[:200],
            )
            if raw.startswith("```"):
                raw = raw.strip("`").strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()

            json_match = re.search(r"\{.*?\}", raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)

            if not raw:
                return self._fallback_decision("Empty decision payload from supervisor LLM")

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                snippet = raw[:160]
                logger.warning(
                    "[SupervisorAgent] Failed to parse decision JSON (len=%s), snippet=%s",
                    len(raw),
                    snippet,
                )
                return self._fallback_decision(
                    f"Non-JSON decision payload, falling back: {snippet}"
                )

            if not isinstance(parsed, dict):
                return self._fallback_decision(
                    f"Decision JSON is not an object/dict: {type(parsed)}"
                )

            return _build_decision(parsed, "string_container_json")

        return self._fallback_decision(f"Unknown result structure: {type(result)}")

    def _rule_based_routing(
        self, user_message: str, state: SessionState, conversation_history: List[dict]
    ) -> SupervisorDecision:
        assessment = self.phase_assessor.assess(state)
        decision = self._offline_route(user_message, state, assessment)
        return self._apply_hard_gates(decision, assessment)

    def offline_route(
        self, user_message: str, state: SessionState, assessment: PhaseAssessment | None = None
    ) -> SupervisorDecision:
        active_assessment = assessment or self.phase_assessor.assess(state)
        decision = self._offline_route(user_message, state, active_assessment)
        return self._apply_hard_gates(decision, active_assessment)
