"""Tests for fabric context in moodboard prompt."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_build_moodboard_prompt_contains_fabric_context_lines():
    fabrics = [
        {
            "fabric_code": "50C4022",
            "color": "grey",
            "pattern": "solid",
            "composition": "cashmere",
        }
    ]

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=fabrics,
        occasion="Business",
        style_keywords=["klassisch"],
        design_preferences={},
    )

    assert "FABRIC CONTEXT" in prompt
    assert "50C4022" in prompt
    assert "grey" in prompt
    assert "cashmere" in prompt
