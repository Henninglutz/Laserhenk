"""Tests for material requirement block in prompts."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_prompt_contains_material_requirement_when_preferred_material_set():
    design_preferences = {"preferred_material": "cashmere"}

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences=design_preferences,
    )

    assert "MATERIAL REQUIREMENT" in prompt
    assert "cashmere" in prompt
