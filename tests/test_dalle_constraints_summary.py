"""Tests for constraints summary in prompts."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_constraints_summary_contains_expected_fields():
    design_preferences = {
        "jacket_front": "single_breasted",
        "wants_vest": False,
        "trouser_color": "navy_blue",
        "requested_fabric_code": "50C4022",
    }

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "50C4022", "color": "grey", "pattern": "solid", "composition": "cashmere"}],
        occasion="Business",
        design_preferences=design_preferences,
    )

    assert "CONSTRAINTS SUMMARY" in prompt
    assert "jacket_front=single_breasted" in prompt
    assert "wants_vest=False" in prompt
    assert "trouser_color=navy_blue" in prompt
    assert "requested_fabric_code=50C4022" in prompt
