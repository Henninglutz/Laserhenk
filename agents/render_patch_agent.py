"""Pydantic-AI agent for extracting structured render patches."""

from __future__ import annotations

import inspect
import logging
import os
from typing import Optional

from models.rendering import (
    JacketPatch,
    NeckwearPatch,
    OutfitPatch,
    PatchDecision,
    ProductParameters,
    ProductPatch,
    VestPatch,
)

logger = logging.getLogger(__name__)

try:  # Optional dependency: allow offline fallback
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via offline path
    PydanticAgent = None


class RenderPatchAgent:
    """Extract structured render patches from user text."""

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        self.model = model
        self.pydantic_agent = None

        if PydanticAgent is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                self.pydantic_agent = PydanticAgent[PatchDecision](model, retries=2)
            except Exception:
                try:
                    self.pydantic_agent = PydanticAgent(
                        model, result_type=PatchDecision, retries=2
                    )
                except Exception:
                    self.pydantic_agent = None
                    logger.warning(
                        "[RenderPatchAgent] Failed to initialize PydanticAgent. Falling back to rules.",
                    )
        elif PydanticAgent is None:
            logger.warning(
                "[RenderPatchAgent] pydantic_ai not installed. Falling back to rules."
            )

        if self.pydantic_agent is not None:
            @self.pydantic_agent.system_prompt
            async def get_system_prompt(ctx) -> str:
                deps = ctx.deps or {}
                return deps.get("system_prompt") or ""

    async def extract_patch_decision(
        self,
        user_message: str,
        params: ProductParameters,
        rag_style_context: Optional[str] = None,
    ) -> PatchDecision:
        if not user_message:
            return PatchDecision(intent="no_change")

        if self.pydantic_agent is None:
            return self._rule_based_decision(user_message)

        system_prompt = self._build_system_prompt(params, rag_style_context)
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
                "[RenderPatchAgent] Pydantic-AI extraction failed: %s. Falling back.",
                exc,
            )
            return self._rule_based_decision(user_message)

    def _build_system_prompt(
        self, params: ProductParameters, rag_style_context: Optional[str]
    ) -> str:
        context = params.model_dump()
        rag_note = rag_style_context or "None"
        return (
            "You extract structured updates to product rendering parameters.\n"
            "Return a PatchDecision object ONLY.\n"
            "Rules:\n"
            "- Do not add or infer fabric information.\n"
            "- Only update fields explicitly requested.\n"
            "- If unclear, return intent=clarify with a single clarifying_question.\n"
            "German mappings:\n"
            "- 'ohne Weste' => outfit.vest.enabled=false\n"
            "- 'mit Weste' or 'drei-tei*' => outfit.vest.enabled=true\n"
            "Current product parameters:\n"
            f"{context}\n"
            "Optional style context (non-fabric):\n"
            f"{rag_note}\n"
        )

    def _rule_based_decision(self, user_message: str) -> PatchDecision:
        text = user_message.lower()
        patch = ProductPatch()
        outfit_patch = patch.outfit or OutfitPatch()
        notes = []

        if "ohne weste" in text:
            vest_patch = outfit_patch.vest or VestPatch()
            vest_patch.enabled = False
            outfit_patch.vest = vest_patch
        if "mit weste" in text or "drei-tei" in text:
            vest_patch = outfit_patch.vest or VestPatch()
            vest_patch.enabled = True
            outfit_patch.vest = vest_patch

        if "tuxedo" in text or "smoking" in text:
            jacket_patch = outfit_patch.jacket or JacketPatch()
            jacket_patch.type = "tuxedo"
            outfit_patch.jacket = jacket_patch
        if "casual" in text or "leger" in text:
            jacket_patch = outfit_patch.jacket or JacketPatch()
            jacket_patch.type = "casual_jacket"
            outfit_patch.jacket = jacket_patch

        if "spitz" in text or "peak" in text:
            jacket_patch = outfit_patch.jacket or JacketPatch()
            jacket_patch.lapel = "peak"
            outfit_patch.jacket = jacket_patch
        if "schalkragen" in text or "shawl" in text:
            jacket_patch = outfit_patch.jacket or JacketPatch()
            jacket_patch.lapel = "shawl"
            outfit_patch.jacket = jacket_patch
        if "notch" in text:
            jacket_patch = outfit_patch.jacket or JacketPatch()
            jacket_patch.lapel = "notch"
            outfit_patch.jacket = jacket_patch

        if "zweireiher" in text or "double breasted" in text:
            jacket_patch = outfit_patch.jacket or JacketPatch()
            jacket_patch.buttons = "double_breasted"
            outfit_patch.jacket = jacket_patch

        if "fliege" in text or "bow tie" in text:
            neckwear_patch = outfit_patch.neckwear or NeckwearPatch()
            neckwear_patch.type = "bow_tie"
            outfit_patch.neckwear = neckwear_patch
        if "ohne krawatte" in text or "ohne schlips" in text:
            neckwear_patch = outfit_patch.neckwear or NeckwearPatch()
            neckwear_patch.type = "none"
            outfit_patch.neckwear = neckwear_patch

        if "minimal" in text or "clean" in text:
            notes.append("Keep the layout minimal and clean.")

        if outfit_patch.model_dump(exclude_none=True):
            patch.outfit = outfit_patch

        if not patch.model_dump(exclude_none=True):
            return PatchDecision(intent="no_change", notes_for_prompt=notes)

        return PatchDecision(
            intent="update_render_params",
            patch=patch,
            notes_for_prompt=notes,
        )
