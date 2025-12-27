import importlib
import os
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services import image_service
from backend.services.image_providers.dalle_provider import DalleProvider
from backend.services.image_providers.imagen_provider import ImagenProvider


def _reset_singleton():
    image_service._image_service = None  # type: ignore


def test_provider_selection_imagen(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "imagen")
    _reset_singleton()
    svc = image_service.get_image_service()
    assert isinstance(svc.provider, ImagenProvider)


def test_provider_selection_dalle(monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "dalle")
    _reset_singleton()
    svc = image_service.get_image_service()
    assert isinstance(svc.provider, DalleProvider)
