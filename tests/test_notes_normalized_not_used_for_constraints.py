"""Ensure notes_normalized does not drive hard constraints."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_trouser_color_not_inferred_from_notes_normalized():
    design_preferences = {"notes_normalized": "please make trousers navy", "trouser_color": None}

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences=design_preferences,
    )

    assert "TROUSERS COLOR" not in prompt
