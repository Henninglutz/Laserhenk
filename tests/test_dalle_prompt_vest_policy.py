"""Tests for vest policy prompt blocks."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_prompt_contains_no_vest_block_when_wants_vest_false():
    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences={"wants_vest": False},
    )

    assert "TWO-PIECE" in prompt
    assert "NO vest" in prompt
    assert "exclude any vest" in prompt


def test_prompt_contains_three_piece_block_when_wants_vest_true():
    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences={"wants_vest": True},
    )

    assert "THREE-PIECE" in prompt
    assert "Vest must be visible" in prompt
