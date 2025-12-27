from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Load .env early (if present) to make settings available across the app
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:  # Fallback to default search path
    load_dotenv()


@dataclass
class Settings:
    image_provider: str = "auto"
    gcp_project: Optional[str] = None
    gcp_location: str = "europe-west4"
    imagen_model: str = "imagen-3.0-generate-002"
    credentials_path: Optional[str] = None
    credentials_json: Optional[str] = None

    def __post_init__(self) -> None:
        self.image_provider = (self.image_provider or "auto").lower()

    def credentials_file_exists(self) -> bool:
        if not self.credentials_path:
            return False
        return Path(self.credentials_path).expanduser().exists()

    def credentials_info(self) -> Optional[dict]:
        if not self.credentials_json:
            return None
        raw = self.credentials_json.strip()
        # Try plain JSON first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Try base64 encoded JSON
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[Settings] Konnte GOOGLE_APPLICATION_CREDENTIALS_JSON nicht dekodieren: %s", exc)
            return None

    def imagen_ready(self) -> bool:
        return bool(self.gcp_project and (self.credentials_file_exists() or self.credentials_info()))


_settings: Optional[Settings] = None


def get_settings(*, force_reload: bool = False, env_file: Optional[str | os.PathLike[str]] = None) -> Settings:
    """Lade Settings aus ENV/.env und cache sie für die Laufzeit."""
    global _settings
    if force_reload or _settings is None:
        if env_file:
            load_dotenv(env_file, override=True)
        _settings = Settings(
            image_provider=os.getenv("IMAGE_PROVIDER", "auto"),
            gcp_project=os.getenv("GCP_PROJECT"),
            gcp_location=os.getenv("GCP_LOCATION", "europe-west4"),
            imagen_model=os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002"),
            credentials_path=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            credentials_json=os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"),
        )
        if not _settings.imagen_ready():
            missing = []
            if not _settings.gcp_project:
                missing.append("GCP_PROJECT")
            if not (_settings.credentials_file_exists() or _settings.credentials_info()):
                missing.append("GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON")
            if missing:
                logger.info("[Settings] Imagen disabled: fehlende Variablen %s", ", ".join(missing))
    return _settings
