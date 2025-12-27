"""Legacy DALLE tool wrapper delegating to ImageService."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.services.image_service import get_image_service, ImageService
from models.api_payload import ImagePolicyDecision
from models.rendering import RenderRequest
from models.tools import DALLEImageRequest, DALLEImageResponse

logger = logging.getLogger(__name__)


class DALLETool:
    def __init__(self, api_key: Optional[str] = None):
        self.service: ImageService = get_image_service()

    async def generate_image(
        self, request: DALLEImageRequest, decision: Optional[ImagePolicyDecision] = None
    ) -> DALLEImageResponse:
        return await self.service.generate_image(request, decision)

    async def generate_mood_board_with_fabrics(
        self,
        fabrics: List[Dict[str, Any]],
        occasion: str,
        style_keywords: Optional[List[str]] = None,
        design_preferences: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        decision: Optional[ImagePolicyDecision] = None,
    ) -> DALLEImageResponse:
        return await self.service.generate_mood_board_with_fabrics(
            fabrics,
            occasion,
            style_keywords=style_keywords,
            design_preferences=design_preferences,
            session_id=session_id,
            decision=decision,
        )

    async def generate_product_sheet(
        self,
        request: RenderRequest,
        notes_for_prompt: Optional[list[str]] = None,
        decision: Optional[ImagePolicyDecision] = None,
    ):
        return await self.service.generate_product_sheet(
            request, notes_for_prompt=notes_for_prompt, decision=decision
        )


# Singleton instance
_dalle_tool: Optional[DALLETool] = None


def get_dalle_tool() -> DALLETool:
    global _dalle_tool
    if _dalle_tool is None:
        _dalle_tool = DALLETool()
        logger.info("[DALLETool] Singleton instance created")
    return _dalle_tool
