"""Tests for optional DALL-E template loading."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.dalle_tool import DALLETool


def test_template_is_prepended_when_path_set(tmp_path, monkeypatch):
    template_file = tmp_path / "template.txt"
    template_file.write_text("TEMPLATE_HEADER", encoding="utf-8")
    monkeypatch.setenv("DALLE_MOODBOARD_TEMPLATE_PATH", str(template_file))

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences={},
    )

    assert prompt.startswith("TEMPLATE_HEADER")


def test_inline_prompt_used_when_no_template_path(monkeypatch):
    monkeypatch.delenv("DALLE_MOODBOARD_TEMPLATE_PATH", raising=False)

    prompt = DALLETool()._build_mood_board_prompt(
        fabrics=[{"fabric_code": "X", "color": "grey", "pattern": "solid", "composition": "wool"}],
        occasion="Business",
        design_preferences={},
    )

    assert "TEMPLATE_HEADER" not in prompt
