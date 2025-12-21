"""Pydantic-AI agent for extracting design preference patches."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from models.patches import PatchDecision

logger = logging.getLogger(__name__)

try:  # Optional dependency: allow offline fallback
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via offline path
    PydanticAgent = None

try:
    from openai import AsyncOpenAI
except ModuleNotFoundError:
    AsyncOpenAI = None


class DesignPatchAgent:
    """Extract structured design patches from user feedback using Pydantic-AI or OpenAI Structured Outputs."""

    def __init__(self, model: str = "openai:gpt-4o-mini", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self.pydantic_agent = None
        self.openai_client = None
        self.use_structured_outputs = False

        # Try Pydantic-AI first (modern API)
        if PydanticAgent is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                system_prompt = self._build_system_prompt()
                self.pydantic_agent = PydanticAgent(
                    model,
                    result_type=PatchDecision,
                    system_prompt=system_prompt,
                )
                logger.info("[DesignPatchAgent] ✅ Initialized with Pydantic-AI")
            except Exception as exc:
                logger.warning(
                    "[DesignPatchAgent] Pydantic-AI initialization failed: %s. Trying OpenAI Structured Outputs.",
                    exc,
                )
                self.pydantic_agent = None
        elif PydanticAgent is None:
            logger.info("[DesignPatchAgent] pydantic_ai not installed. Using OpenAI Structured Outputs.")

        # Fallback to OpenAI Structured Outputs
        if self.pydantic_agent is None and AsyncOpenAI is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                self.openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                self.use_structured_outputs = True
                logger.info("[DesignPatchAgent] ✅ Initialized with OpenAI Structured Outputs (beta)")
            except Exception as exc:
                logger.warning("[DesignPatchAgent] OpenAI client initialization failed: %s", exc)

    async def extract_patch_decision(
        self, user_message: str, context: Optional[str] = None
    ) -> PatchDecision:
        """
        Extract structured PatchDecision from user feedback.

        Uses Pydantic-AI if available, otherwise falls back to OpenAI Structured Outputs.

        Args:
            user_message: User feedback message
            context: Optional context information

        Returns:
            PatchDecision with extracted design preferences
        """
        if not user_message:
            return PatchDecision(confidence=0.0)

        # Route 1: Pydantic-AI
        if self.pydantic_agent is not None:
            try:
                result = await self.pydantic_agent.run(user_message)
                decision = result.data if hasattr(result, "data") else result

                if isinstance(decision, PatchDecision):
                    logger.info(
                        "[DesignPatchAgent] ✅ Pydantic-AI extraction successful: confidence=%.2f, changed_fields=%s",
                        decision.confidence,
                        decision.changed_fields,
                    )
                    return decision

                return PatchDecision.model_validate(decision)
            except Exception as exc:
                logger.warning(
                    "[DesignPatchAgent] Pydantic-AI extraction failed: %s. Trying fallback.",
                    exc,
                )

        # Route 2: OpenAI Structured Outputs (beta)
        if self.use_structured_outputs and self.openai_client is not None:
            try:
                return await self._extract_via_structured_outputs(user_message)
            except Exception as exc:
                logger.warning(
                    "[DesignPatchAgent] OpenAI Structured Outputs extraction failed: %s",
                    exc,
                )

        # Route 3: Fallback - return empty decision
        logger.warning("[DesignPatchAgent] No extraction backend available, returning empty decision")
        return PatchDecision(
            confidence=0.0,
            clarification_questions=[
                "Bitte präzisieren Sie die gewünschten Änderungen am Design."
            ],
        )

    async def _extract_via_structured_outputs(self, user_message: str) -> PatchDecision:
        """
        Extract PatchDecision using OpenAI Structured Outputs (beta).

        Args:
            user_message: User feedback message

        Returns:
            PatchDecision
        """
        system_prompt = self._build_system_prompt()

        # Use beta.chat.completions.parse for structured outputs
        completion = await self.openai_client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",  # Structured outputs require this model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format=PatchDecision,
            temperature=self.temperature,
        )

        decision = completion.choices[0].message.parsed

        logger.info(
            "[DesignPatchAgent] ✅ OpenAI Structured Outputs extraction successful: confidence=%.2f, changed_fields=%s",
            decision.confidence,
            decision.changed_fields,
        )

        return decision

    def _build_system_prompt(self, context: Optional[str] = None) -> str:
        """Build system prompt for PatchDecision extraction."""
        return """Du bist ein Experte für die Extraktion von Design-Präferenzen aus Nutzerfeedback.

AUFGABE:
Extrahiere strukturierte PatchDecision aus dem Nutzerfeedback und gib confidence + changed_fields zurück.

MAPPING-REGELN (Deutsche Synonyme → Strukturierte Felder):

**Jacket Front (jacket_front):**
- "Einreiher" | "einreihig" | "single-breasted" | "eine Knopfreihe" → "single_breasted"
- "Zweireiter" | "zweireihig" | "double-breasted" | "zwei Knopfreihen" → "double_breasted"

**Lapel Style (lapel_style):**
- "Spitzrevers" | "Peak" | "peak lapel" → "peak"
- "Stegrevers" | "Schlitzrevers" | "Notch" → "notch"
- "Schalkragen" | "Shawl" → "shawl"

**Lapel Roll (lapel_roll):**
- "fallendes Revers" | "rollierendes Revers" | "Facon" | "rolling lapel" → "rolling"
- "flaches Revers" | "flat lapel" → "flat"

**Shoulder Padding (shoulder_padding):**
- "ohne Schulterpolster" | "keine Polster" | "spalla camicia" → "none"
- "leicht" | "light" | "minimal" → "light"
- "mittel" | "medium" | "normal" → "medium"
- "stark" | "structured" | "ausgeprägt" → "structured"

**Trouser Front (trouser_front):**
- "Bundfalte" | "Falten" | "pleats" | "mit Falte" → "pleats"
- "glatt" | "ohne Falte" | "flat front" → "flat_front"

**Vest/Waistcoat (wants_vest):**
- "ohne Weste" | "kein Gilet" | "Zweiteiler" | "no vest" → false
- "mit Weste" | "Gilet" | "Dreiteiler" | "with vest" → true

**Neckwear (neckwear):**
- "Fliege" | "Schleife" | "bow tie" → "bow_tie"
- "Krawatte" | "tie" → "tie"
- "ohne" | "none" → "none"

**Button Count (button_count):**
- "ein Knopf" | "single button" → 1
- "zwei Knöpfe" | "two buttons" → 2
- "drei Knöpfe" | "three buttons" → 3

**Fabric Code (requested_fabric_code):**
- "anderer Stoff: XXXXX" | "Stoff: XXXXX" | "neuer Stoff XXXXX" → extract "XXXXX"
- Fabric codes are typically alphanumeric (e.g., "50C4022", "10M5000", "20W3000")
- Extract EXACTLY as user provides it (case-sensitive)
- Examples:
  - "Nein, anderer Stoff: 50C4022" → requested_fabric_code="50C4022"
  - "lieber Stoff 10M5000" → requested_fabric_code="10M5000"

WICHTIGE REGELN:
1. Erkenne deutsche Synonyme, Flexionen und Tippfehler (z.B. "schulterpolter", "fallende revers")
2. Setze confidence=0.0 wenn unklar, confidence=0.5-0.8 wenn teilweise sicher, confidence=0.9-1.0 wenn sehr sicher
3. Fülle changed_fields[] mit allen geänderten Feldern (z.B. ["jacket_front", "lapel_roll"])
4. Bevorzuge 'unknown' statt Halluzinationen bei Unsicherheit
5. Kein RAG, keine Datenbankabfragen - nur das User-Feedback analysieren

BEISPIELE:

Input: "bitte nochmal als Einreiher und mit fallendem Revers"
Output:
{
  "patch": {
    "jacket_front": "single_breasted",
    "lapel_roll": "rolling"
  },
  "confidence": 0.95,
  "changed_fields": ["jacket_front", "lapel_roll"]
}

Input: "ohne Weste bitte"
Output:
{
  "patch": {
    "wants_vest": false
  },
  "session_patch": {
    "wants_vest": false
  },
  "confidence": 1.0,
  "changed_fields": ["wants_vest"]
}

Input: "modern, leicht, italienisch, ohne Futter ohne Polster"
Output:
{
  "patch": {
    "shoulder_padding": "none",
    "notes_normalized": "modern italienisch leicht ohne Futter"
  },
  "confidence": 0.85,
  "changed_fields": ["shoulder_padding", "notes_normalized"]
}

Input: "Nein, anderer Stoff: 50C4022"
Output:
{
  "patch": {
    "requested_fabric_code": "50C4022"
  },
  "confidence": 0.95,
  "changed_fields": ["requested_fabric_code"]
}
"""
