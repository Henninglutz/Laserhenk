"""Tests for prompt loading and usage tracking."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.prompt_loader import PROMPT_FILES, prompt_registry


def test_prompt_usage_tracking():
    """Prompt registry should track load time, last use, and usage count."""
    prompt_registry.reset()

    # First access loads from disk
    content = prompt_registry.get_prompt("core")
    assert "HENK Core Prompt" in content

    usage = prompt_registry.get_usage_report()["core"]
    assert usage["use_count"] == 1
    assert usage["loaded_at"] is not None
    assert usage["last_used_at"] is not None

    # Second access increments use counter but keeps same path
    prompt_registry.get_prompt("core")
    updated_usage = prompt_registry.get_usage_report()["core"]
    assert updated_usage["use_count"] == 2
    assert updated_usage["path"].endswith(PROMPT_FILES["core"])



def test_unknown_prompt_key_raises():
    """Unknown prompt names should raise a KeyError."""
    prompt_registry.reset()
    try:
        prompt_registry.get_prompt("unknown")
    except KeyError:
        pass
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected KeyError for unknown prompt name")
