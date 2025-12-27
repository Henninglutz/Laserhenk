from io import BytesIO
from pathlib import Path
import sys

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.prompts.loader import PromptLoader
from backend.services.image_service import ImageService
from backend.services.image_providers.base import ImageProvider

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


class FakeProvider(ImageProvider):
    name = "imagen"

    async def generate(self, prompt: str, *, size=None, quality=None, n: int = 1):
        buf = BytesIO()
        Image.new("RGB", (100, 100), (0, 0, 255)).save(buf, format="PNG")
        return [buf.getvalue()]


@pytest.mark.asyncio
async def test_composite_creation(monkeypatch, tmp_path):
    if Image is None:
        pytest.skip("Pillow not installed")

    project_root = Path(__file__).resolve().parents[1]
    fabrics_dir = project_root / "storage" / "fabrics"
    fabrics_dir.mkdir(parents=True, exist_ok=True)
    fabric_path = fabrics_dir / "test.png"
    Image.new("RGB", (50, 50), (255, 0, 0)).save(fabric_path, format="PNG")

    monkeypatch.chdir(tmp_path)

    service = ImageService(provider=FakeProvider(), prompt_loader=PromptLoader())
    fabrics = [
        {
            "fabric_code": "FAB1",
            "image_url": "/fabrics/test.png",
            "color": "red",
            "pattern": "solid",
            "composition": "wool",
        }
    ]

    response = await service.generate_mood_board_with_fabrics(
        fabrics, occasion="Business", style_keywords=["modern"], design_preferences={}
    )

    assert response.success
    assert response.local_path

    composite = Image.open(response.local_path)
    assert composite.size == (100, 100)
    assert composite.getpixel((90, 90)) != (0, 0, 255)
