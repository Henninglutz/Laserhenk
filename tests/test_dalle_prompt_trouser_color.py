"""Tests for structured trouser color prompt handling."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_build_moodboard_prompt_includes_structured_trouser_color_instruction():
    fabrics = [
        {
            "fabric_code": "50C4022",
            "color": "grey",
            "pattern": "solid",
            "composition": "cashmere",
        }
    ]
    design_preferences = {"trouser_color": "navy_blue", "jacket_front": "single_breasted"}

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=fabrics,
        occasion="Business",
        style_keywords=["klassisch"],
        design_preferences=design_preferences,
    )

    assert "TROUSERS COLOR: navy blue" in prompt
    assert "contrast trousers" in prompt
