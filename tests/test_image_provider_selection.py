import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services import image_service
import backend.services.image_providers.imagen_provider as imagen_provider
import backend.settings as settings
from backend.services.image_providers.dalle_provider import DalleProvider
from backend.services.image_providers.imagen_provider import ImagenProvider


def _reset_singleton():
    image_service._image_service = None  # type: ignore
    settings._settings = None  # type: ignore


def test_provider_selection_imagen(monkeypatch, tmp_path):
    class DummyCred:
        token = "token"
        valid = False

        def refresh(self, request):  # pragma: no cover - simple stub
            self.valid = True
            self.token = "refreshed"

    class DummyCreds:
        @staticmethod
        def from_service_account_file(path, scopes=None):  # pragma: no cover - simple stub
            return DummyCred()

        @staticmethod
        def from_service_account_info(info, scopes=None):  # pragma: no cover - simple stub
            return DummyCred()

    cred_file = tmp_path / "creds.json"
    cred_file.write_text("{}")

    monkeypatch.setattr(imagen_provider.service_account, "Credentials", DummyCreds)
    monkeypatch.setenv("IMAGE_PROVIDER", "imagen")
    monkeypatch.setenv("GCP_PROJECT", "proj")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(cred_file))
    _reset_singleton()
    svc = image_service.get_image_service()
    assert isinstance(svc.provider, ImagenProvider)


def test_provider_selection_imagen_without_config_falls_back(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "imagen")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    _reset_singleton()
    svc = image_service.get_image_service()
    assert isinstance(svc.provider, DalleProvider)


def test_provider_selection_dalle(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "dalle")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    _reset_singleton()
    svc = image_service.get_image_service()
    assert isinstance(svc.provider, DalleProvider)
