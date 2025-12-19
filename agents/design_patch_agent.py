"""Pydantic-AI agent for extracting design preference patches."""

from __future__ import annotations

import inspect
import logging
import os
from typing import Optional

from models.patches import PatchDecision

logger = logging.getLogger(__name__)

try:  # Optional dependency: allow offline fallback
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via offline path
    PydanticAgent = None


class DesignPatchAgent:
    """Extract structured design patches from user feedback."""

    def __init__(self, model: str = "openai:gpt-4o-mini", temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self.pydantic_agent = None

        if PydanticAgent is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                self.pydantic_agent = PydanticAgent[PatchDecision](
                    model, retries=1, temperature=temperature
                )
            except Exception:
                try:
                    self.pydantic_agent = PydanticAgent(
                        model,
                        result_type=PatchDecision,
                        retries=1,
                        temperature=temperature,
                    )
                except Exception:
                    self.pydantic_agent = None
                    logger.warning(
                        "[DesignPatchAgent] Failed to initialize PydanticAgent. Falling back.",
                    )
        elif PydanticAgent is None:
            logger.warning(
                "[DesignPatchAgent] pydantic_ai not installed. Falling back."
            )

        if self.pydantic_agent is not None:
            @self.pydantic_agent.system_prompt
            async def get_system_prompt(ctx) -> str:
                deps = ctx.deps or {}
                return deps.get("system_prompt") or ""

    async def extract_patch_decision(
        self, user_message: str, context: Optional[str] = None
    ) -> PatchDecision:
        if not user_message:
            return PatchDecision(confidence=0.0)

        if self.pydantic_agent is None:
            return PatchDecision(
                confidence=0.0,
                clarification_questions=[
                    "Bitte präzisieren Sie die gewünschten Änderungen am Design."
                ],
            )

        system_prompt = self._build_system_prompt(context)

        try:
            base_kwargs = {"deps": {"system_prompt": system_prompt}}
            run_sig = inspect.signature(self.pydantic_agent.run)
            allowed_params = set(run_sig.parameters.keys())
            run_kwargs = {
                key: value for key, value in base_kwargs.items() if key in allowed_params
            }
            if "response_format" in allowed_params:
                run_kwargs["response_format"] = {"type": "json_object"}

            use_result_type = "result_type" in allowed_params
            if use_result_type:
                result = await self.pydantic_agent.run(
                    user_message, result_type=PatchDecision, **run_kwargs
                )
            else:
                result = await self.pydantic_agent.run(user_message, **run_kwargs)

            decision = result.data if hasattr(result, "data") else result
            if isinstance(decision, PatchDecision):
                return decision
            return PatchDecision.model_validate(decision)
        except Exception as exc:
            logger.warning(
                "[DesignPatchAgent] Extraction failed: %s. Returning clarification.",
                exc,
            )
            return PatchDecision(
                confidence=0.0,
                clarification_questions=[
                    "Können Sie die gewünschten Änderungen noch einmal kurz zusammenfassen?"
                ],
            )

    def _build_system_prompt(self, context: Optional[str]) -> str:
        return (
            "Du extrahierst eine strukturierte PatchDecision aus Nutzerfeedback.\n"
            "Regeln:\n"
            "- Antworte ausschließlich mit gültigem JSON für PatchDecision.\n"
            "- Erkenne deutsche Synonyme, Flexionen und Tippfehler (z.B. 'schulterpolter', 'fallende revers').\n"
            "- Bevorzuge 'unknown' statt Halluzinationen.\n"
            "- Kein RAG, keine Datenbankabfragen.\n"
            "Mapping-Hinweise:\n"
            "- Weste/Waistcoat/Gilet => wants_vest\n"
            "- einreihig/eine Knopfreihe/single-breasted => jacket_front=single_breasted\n"
            "- zweireihig/double-breasted => jacket_front=double_breasted\n"
            "- fallendes/rollierendes Revers/Facon => lapel_roll=rolling\n"
            "- Spitzrevers/Peak => lapel_style=peak\n"
            "- Schlitzrevers/Notch => lapel_style=notch\n"
            "- Schalkragen/Shawl => lapel_style=shawl\n"
            "- ohne Schulterpolster/spalla camicia => shoulder_padding=none oder light\n"
            "- Bundfalte/pleats => trouser_front=pleats\n"
            "- Fliege/Schleife => neckwear=bow_tie\n"
            "- Krawatte => neckwear=tie\n"
            "Kontext:\n"
            f"{context or 'Kein zusätzlicher Kontext'}\n"
        )
