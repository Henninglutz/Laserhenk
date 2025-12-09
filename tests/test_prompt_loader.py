"""Tests for prompt loading and usage tracking."""

import sys
from pathlib import Path

import pytest

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
    first_loaded_at = usage["loaded_at"]

    # Second access increments use counter but keeps same path
    prompt_registry.get_prompt("core")
    updated_usage = prompt_registry.get_usage_report()["core"]
    assert updated_usage["use_count"] == 2
    assert updated_usage["path"].endswith(PROMPT_FILES["core"])
    assert updated_usage["loaded_at"] == first_loaded_at



def test_unknown_prompt_key_raises():
    """Unknown prompt names should raise a KeyError."""
    prompt_registry.reset()
    try:
        prompt_registry.get_prompt("unknown")
    except KeyError:
        pass
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected KeyError for unknown prompt name")


def test_prompt_or_default_falls_back_to_core():
    """Unknown prompts should fall back to the core prompt by default."""
    prompt_registry.reset()

    content = prompt_registry.get_prompt_or_default("does_not_exist")

    assert "HENK Core Prompt" in content
    usage = prompt_registry.get_usage_report()

    assert "core" in usage
    assert usage["core"]["use_count"] == 1
    assert "does_not_exist" not in usage


def test_prompt_or_default_raises_if_fallback_unknown():
    """An unknown fallback should still raise a KeyError for visibility."""
    prompt_registry.reset()

    with pytest.raises(KeyError):
        prompt_registry.get_prompt_or_default("missing_prompt", fallback_name="nope")
