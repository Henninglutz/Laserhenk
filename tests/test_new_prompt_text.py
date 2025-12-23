"""Tests for the new DALL-E prompt template text."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_new_prompt_includes_photorealistic_header_and_garments_block():
    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences={"wants_vest": False},
    )

    assert "Ultra-photorealistic professional fashion photograph" in prompt
    assert "GARMENTS:" in prompt
