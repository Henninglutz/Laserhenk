from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import List

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from .base import ImageProvider

logger = logging.getLogger(__name__)


class ImagenProvider(ImageProvider):
    name = "imagen"

    def __init__(
        self,
        *,
        project: str | None = None,
        location: str | None = None,
        model: str | None = None,
        credentials_path: str | None = None,
    ):
        self.project = project or os.getenv("GCP_PROJECT")
        self.location = location or os.getenv("GCP_LOCATION", "europe-west4")
        self.model = model or os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.credentials = None
        if self.credentials_path:
            self.credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

    async def generate(
        self, prompt: str, *, size: str | None = None, quality: str | None = None, n: int = 1
    ) -> List[bytes]:
        if not self.project:
            raise RuntimeError("GCP_PROJECT not configured for Imagen provider")
        if not self.credentials:
            raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS not configured for Imagen provider")

        token = await asyncio.get_event_loop().run_in_executor(None, self._refresh_token)
        url = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project}/"
            f"locations/{self.location}/publishers/google/models/{self.model}:predict"
        )

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": n},
        }
        if size:
            payload["parameters"]["size"] = size
        if quality:
            payload["parameters"]["quality"] = quality

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        logger.info("[ImagenProvider] Requesting image generation")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        predictions = data.get("predictions") or []
        if not predictions:
            raise RuntimeError("No predictions returned by Imagen")

        images: List[bytes] = []
        for item in predictions:
            b64_img = (
                item.get("bytesBase64Encoded")
                or item.get("image")
                or item.get("b64_json")
            )
            if not b64_img:
                raise RuntimeError("Missing base64 image in prediction")
            images.append(base64.b64decode(b64_img))

        return images

    def _refresh_token(self) -> str:
        assert self.credentials is not None
        if not self.credentials.valid:
            self.credentials.refresh(Request())
        return str(self.credentials.token)
