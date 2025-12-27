import os
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import backend.settings as settings
from backend.settings import get_settings


def reset_settings():
    settings._settings = None  # type: ignore


def test_settings_loads_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    cred_file = tmp_path / "svc.json"
    cred_file.write_text("{}")
    env_file.write_text(
        "\n".join(
            [
                "IMAGE_PROVIDER=imagen",
                "GCP_PROJECT=my-proj",
                f"GOOGLE_APPLICATION_CREDENTIALS={cred_file}",
                "GCP_LOCATION=custom-loc",
                "IMAGEN_MODEL=custom-model",
            ]
        )
    )
    reset_settings()
    loaded = get_settings(force_reload=True, env_file=env_file)
    assert loaded.gcp_project == "my-proj"
    assert loaded.gcp_location == "custom-loc"
    assert loaded.imagen_model == "custom-model"
    assert loaded.credentials_file_exists()
    assert loaded.imagen_ready() is True


def test_settings_inline_credentials(monkeypatch):
    reset_settings()
    monkeypatch.setenv("IMAGE_PROVIDER", "imagen")
    monkeypatch.setenv("GCP_PROJECT", "inline-proj")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "{\"type\": \"service_account\"}")
    loaded = get_settings(force_reload=True)
    assert loaded.credentials_info() == {"type": "service_account"}


@pytest.mark.asyncio
async def test_imagen_provider_missing_credentials_does_not_crash_init():
    from backend.services.image_providers.imagen_provider import ImagenProvider

    provider = ImagenProvider(project="proj", credentials_path="/does/not/exist.json")
    assert provider.credentials is None


@pytest.mark.asyncio
async def test_imagen_provider_generate_raises_clear_error_when_missing_config(monkeypatch):
    from backend.services.image_providers.imagen_provider import ImagenProvider

    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    provider = ImagenProvider(project=None, credentials_path=None)
    with pytest.raises(RuntimeError) as err:
        await provider.generate("prompt")
    assert "Imagen disabled" in str(err.value)


def test_provider_selection_falls_back_when_imagen_invalid(monkeypatch):
    from backend.services.image_providers.dalle_provider import DalleProvider
    from backend.services import image_service

    monkeypatch.setenv("IMAGE_PROVIDER", "imagen")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    reset_settings()
    image_service._image_service = None  # type: ignore
    svc = image_service.get_image_service()
    assert isinstance(svc.provider, DalleProvider)
