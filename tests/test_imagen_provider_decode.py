import base64
from io import BytesIO
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.image_providers.imagen_provider import ImagenProvider

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_imagen_provider_decodes_base64(monkeypatch, tmp_path):
    if Image is None:
        pytest.skip("Pillow not installed")

    # Create simple 1x1 image
    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 0, 0)).save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    payload = {"predictions": [{"bytesBase64Encoded": img_b64}]}

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return DummyResponse(payload)

    monkeypatch.setattr("httpx.AsyncClient", DummyClient)
    provider = ImagenProvider(project="proj", credentials_path=None)
    provider.credentials = object()  # bypass real credentials
    provider._refresh_token = lambda: "token"  # type: ignore

    images = await provider.generate("prompt")
    assert len(images) == 1
    img = Image.open(BytesIO(images[0]))
    assert img.size == (1, 1)
