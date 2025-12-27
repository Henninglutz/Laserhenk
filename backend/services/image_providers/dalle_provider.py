from __future__ import annotations

import base64
import logging
import os
from typing import List

import requests
from openai import AsyncOpenAI

from .base import ImageProvider

logger = logging.getLogger(__name__)


class DalleProvider(ImageProvider):
    name = "dalle"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.last_revised_prompt: str | None = None

    async def generate(
        self, prompt: str, *, size: str | None = None, quality: str | None = None, n: int = 1
    ) -> List[bytes]:
        if not self.client:
            raise RuntimeError("OpenAI client not configured")

        logger.info("[DalleProvider] Generating image")
        response = await self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size or "1024x1024",
            quality=quality or "standard",
            n=n,
        )

        results: List[bytes] = []
        self.last_revised_prompt = getattr(response.data[0], "revised_prompt", None)

        for item in response.data:
            if getattr(item, "b64_json", None):
                results.append(base64.b64decode(item.b64_json))
                continue
            if getattr(item, "url", None):
                results.append(self._download(item.url))
                continue
            raise RuntimeError("Unexpected DALL-E response format")

        return results

    def _download(self, url: str) -> bytes:
        logger.info("[DalleProvider] Downloading image from url response")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content
