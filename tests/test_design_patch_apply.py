"""Tests for design preference patch application."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.customer import DesignPreferences
from models.patches import DesignPreferencesPatch, apply_design_preferences_patch


def test_apply_design_preferences_patch_applies_vest_and_fabric_code():
    existing = DesignPreferences(wants_vest=None, requested_fabric_code=None)
    patch = DesignPreferencesPatch(wants_vest=False, requested_fabric_code="50C4022")

    updated = apply_design_preferences_patch(existing, patch)

    assert updated.wants_vest is False
    assert updated.requested_fabric_code == "50C4022"
