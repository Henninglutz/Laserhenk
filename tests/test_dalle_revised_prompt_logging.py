"""Tests for revised prompt logging warnings."""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool
from models.tools import DALLEImageRequest


class _FakeImage:
    def __init__(self, url: str, revised_prompt: str):
        self.url = url
        self.revised_prompt = revised_prompt


class _FakeImages:
    def __init__(self, revised_prompt: str):
        self._revised_prompt = revised_prompt

    async def generate(self, **_kwargs):
        return type("Resp", (), {"data": [_FakeImage("http://example.com", self._revised_prompt)]})()


class _FakeClient:
    def __init__(self, revised_prompt: str):
        self.images = _FakeImages(revised_prompt)


@pytest.mark.asyncio
async def test_generate_image_warns_if_constraint_missing_in_revised_prompt(caplog):
    tool = DALLETool(api_key="test")
    tool.client = _FakeClient(revised_prompt="Create a photo without constraint block")
    tool.enabled = True

    request = DALLEImageRequest(prompt="CRITICAL: NO vest. CONSTRAINTS SUMMARY.")

    caplog.set_level("WARNING")
    await tool.generate_image(request=request)

    warnings = [record.message for record in caplog.records if record.levelname == "WARNING"]
    assert any("Revised prompt dropped constraint token" in msg for msg in warnings)
