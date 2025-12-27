"""Image policy routing and payload helpers."""

from __future__ import annotations

import logging
import os
from typing import Optional

from models.api_payload import FabricRef, ImagePolicyDecision
from models.customer import SessionState

logger = logging.getLogger(__name__)

try:  # Optional dependency
    from pydantic_ai import Agent as PydanticAgent  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional
    PydanticAgent = None


EXPLICIT_OPT_IN_PHRASES = [
    "illustrative moodboard",
    "illustrative mood board",
    "illustrative",
    "illustration",
    "dalle",
    "generate a moodboard",
    "generate a mood board",
    "zeichne",
    "illustration bitte",
    "bitte illustrieren",
]


def _has_rag_images(rag_context: Optional[dict]) -> bool:
    fabrics = (rag_context or {}).get("fabrics") or []
    for fabric in fabrics:
        image_urls = fabric.get("image_urls") or []
        if isinstance(image_urls, dict):
            image_urls = [val for val in image_urls.values() if val]
        local_paths = fabric.get("local_image_paths") or []
        if any(url for url in image_urls) or any(path for path in local_paths):
            return True
    return False


def _explicit_opt_in(text: str) -> bool:
    lowered = (text or "").lower()
    if not lowered:
        return False
    return any(phrase in lowered for phrase in EXPLICIT_OPT_IN_PHRASES)


def collect_fabric_refs(state: SessionState) -> list[FabricRef]:
    """Collect fabric references from RAG context or shown fabrics."""
    refs: list[FabricRef] = []
    rag_context = state.rag_context or {}
    fabrics = rag_context.get("fabrics") or []

    for fabric in fabrics:
        raw_image_urls = fabric.get("image_urls") or []
        if isinstance(raw_image_urls, dict):
            raw_image_urls = [val for val in raw_image_urls.values() if val]
        image_urls = [url for url in raw_image_urls if url]
        local_paths = [
            path
            for path in (fabric.get("local_image_paths") or [])
            if path
        ]
        urls = image_urls or local_paths
        if not urls:
            continue
        refs.append(
            FabricRef(
                fabric_id=str(fabric.get("fabric_id") or fabric.get("id") or "") or None,
                fabric_code=fabric.get("fabric_code") or fabric.get("reference"),
                name=fabric.get("name"),
                color=fabric.get("color"),
                pattern=fabric.get("pattern"),
                composition=fabric.get("composition") or fabric.get("material"),
                category=fabric.get("category"),
                price_category=fabric.get("price_category") or fabric.get("price_tier"),
                image_urls=urls,
            )
        )

    if refs:
        return refs

    for fabric in state.shown_fabric_images or []:
        url = fabric.get("url") or fabric.get("image_url")
        if not url:
            continue
        refs.append(
            FabricRef(
                fabric_id=None,
                fabric_code=fabric.get("fabric_code") or fabric.get("reference"),
                name=fabric.get("name"),
                color=fabric.get("color"),
                pattern=fabric.get("pattern"),
                composition=fabric.get("composition") or fabric.get("material"),
                category=fabric.get("category"),
                price_category=fabric.get("price_category") or fabric.get("price_tier"),
                image_urls=[url],
            )
        )

    return refs


def collect_image_urls_from_refs(refs: list[FabricRef]) -> list[str]:
    urls: list[str] = []
    for ref in refs:
        for url in ref.image_urls:
            if url and url not in urls:
                urls.append(url)
    return urls


class ImagePolicyAgent:
    """Pydantic-AI assisted image policy routing with hard gates."""

    def __init__(self, model: str = "openai:gpt-4o-mini") -> None:
        self.model = model
        self.pydantic_agent = None

        if PydanticAgent is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                self.pydantic_agent = PydanticAgent[ImagePolicyDecision](model, retries=2)
            except Exception:
                self.pydantic_agent = None
                logger.warning(
                    "[ImagePolicyAgent] Failed to initialize PydanticAgent, using rules only."
                )
        elif PydanticAgent is None:
            logger.warning(
                "[ImagePolicyAgent] pydantic_ai not installed; using rules only."
            )

        if self.pydantic_agent is not None:
            @self.pydantic_agent.system_prompt
            async def get_system_prompt(ctx) -> str:
                deps = ctx.deps or {}
                return deps.get("system_prompt") or ""

    async def decide(
        self,
        user_message: str,
        state: SessionState,
        supervisor_allows_dalle: bool = False,
    ) -> ImagePolicyDecision:
        rag_context = state.rag_context or {}
        has_rag_images = _has_rag_images(rag_context)
        has_uploads = bool(state.image_state.user_uploads)
        wants_illustration = _explicit_opt_in(user_message)
        dalle_enabled = os.getenv("ENABLE_DALLE", "false").lower() == "true"

        base_decision = ImagePolicyDecision(
            want_images=wants_illustration or has_rag_images or has_uploads,
            allowed_source="dalle" if wants_illustration else "none",
            rationale="Rule-based image policy",
            required_fabric_images=True,
            max_images=2,
        )

        if self.pydantic_agent is not None:
            system_prompt = (
                "Return ImagePolicyDecision JSON. "
                "Never allow DALL·E unless explicitly requested and permitted."
            )
            try:
                result = await self.pydantic_agent.run(
                    user_message,
                    deps={"system_prompt": system_prompt},
                    result_type=ImagePolicyDecision,
                )
                if hasattr(result, "data"):
                    base_decision = result.data  # type: ignore[assignment]
                elif hasattr(result, "result"):
                    base_decision = result.result  # type: ignore[assignment]
                elif isinstance(result, ImagePolicyDecision):
                    base_decision = result
            except Exception as exc:  # pragma: no cover - optional LLM failure
                logger.warning("[ImagePolicyAgent] LLM decision failed: %s", exc)

        if has_rag_images:
            return ImagePolicyDecision(
                want_images=True,
                allowed_source="rag",
                rationale="RAG fabric images available; use real fabrics.",
                required_fabric_images=True,
                max_images=2,
                block_reason=None,
            )

        if has_uploads:
            return ImagePolicyDecision(
                want_images=True,
                allowed_source="upload",
                rationale="User uploaded fabric images available.",
                required_fabric_images=True,
                max_images=2,
                block_reason=None,
            )

        if base_decision.allowed_source == "dalle" and wants_illustration:
            if dalle_enabled and supervisor_allows_dalle:
                return ImagePolicyDecision(
                    want_images=True,
                    allowed_source="dalle",
                    rationale="Explicit illustrative request and supervisor allowed.",
                    required_fabric_images=False,
                    max_images=2,
                    block_reason=None,
                )
            return ImagePolicyDecision(
                want_images=False,
                allowed_source="none",
                rationale="DALL·E request blocked by policy.",
                required_fabric_images=False,
                max_images=0,
                block_reason="DALL·E not enabled or supervisor did not allow it.",
            )

        return ImagePolicyDecision(
            want_images=False,
            allowed_source="none",
            rationale="No fabric images available; text-only required.",
            required_fabric_images=True,
            max_images=0,
            block_reason="Bitte Stoffbild hochladen oder Stoff aus dem Katalog auswählen.",
        )
