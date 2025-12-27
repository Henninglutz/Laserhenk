from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from pathlib import Path
from typing import List, Optional

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
        credentials_json: str | None = None,
    ):
        self.project = project or os.getenv("GCP_PROJECT")
        self.location = location or os.getenv("GCP_LOCATION", "europe-west4")
        self.model = model or os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.credentials_json = credentials_json or os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        self.credentials = None

        info = self._load_credentials_info()
        if info:
            self.credentials = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        elif self.credentials_path and Path(self.credentials_path).expanduser().exists():
            self.credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        else:
            if self.credentials_path:
                logger.warning(
                    "[ImagenProvider] Credentials file nicht gefunden: %s", self.credentials_path
                )
            elif self.credentials_json:
                logger.warning("[ImagenProvider] Credentials JSON konnte nicht geladen werden")
            else:
                logger.warning("[ImagenProvider] Keine Imagen-Credentials konfiguriert")

    async def generate(
        self, prompt: str, *, size: str | None = None, quality: str | None = None, n: int = 1
    ) -> List[bytes]:
        if not self.project:
            raise RuntimeError("Imagen disabled: missing GCP_PROJECT")
        if not self.credentials:
            raise RuntimeError(
                "Imagen disabled: missing GOOGLE_APPLICATION_CREDENTIALS / GOOGLE_APPLICATION_CREDENTIALS_JSON"
            )

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

    def _load_credentials_info(self) -> Optional[dict]:
        if not self.credentials_json:
            return None
        raw = self.credentials_json.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            try:
                decoded = base64.b64decode(raw).decode("utf-8")
                return json.loads(decoded)
            except Exception:  # pragma: no cover - defensive
                return None
