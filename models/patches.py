"""Structured patch models for DesignHenk feedback."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from models.customer import DesignPreferences


class DesignPreferencesPatch(BaseModel):
    """Patch for DesignPreferences."""

    wants_vest: Optional[bool] = None
    jacket_front: Optional[Literal["single_breasted", "double_breasted"]] = None
    button_count: Optional[Literal[1, 2, 3]] = None
    lapel_style: Optional[Literal["notch", "peak", "shawl", "unknown"]] = None
    lapel_roll: Optional[Literal["rolling", "flat", "unknown"]] = None
    shoulder_padding: Optional[
        Literal["none", "light", "medium", "structured", "unknown"]
    ] = None
    trouser_front: Optional[Literal["pleats", "flat_front", "unknown"]] = None
    neckwear: Optional[Literal["tie", "bow_tie", "none", "unknown"]] = None
    notes_normalized: Optional[str] = Field(
        None, max_length=120, description="Normalized short notes"
    )
    requested_fabric_code: Optional[str] = Field(
        None,
        max_length=20,
        description="Fabric code requested by user (e.g., '50C4022', '10M5000')"
    )


class SessionStatePatch(BaseModel):
    """Patch for SessionState fields."""

    wants_vest: Optional[bool] = None


class PatchDecision(BaseModel):
    """Top-level patch decision output."""

    patch: DesignPreferencesPatch = Field(default_factory=DesignPreferencesPatch)
    session_patch: Optional[SessionStatePatch] = None
    confidence: float = Field(ge=0.0, le=1.0)
    changed_fields: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


def apply_design_preferences_patch(
    existing: DesignPreferences, patch: DesignPreferencesPatch
) -> DesignPreferences:
    """Apply design patch to DesignPreferences, ignoring unknown values."""
    updated = existing.model_copy(deep=True)

    def _set(attr: str, value):
        if value is None:
            return
        if isinstance(value, str) and value == "unknown":
            return
        setattr(updated, attr, value)

    _set("jacket_front", patch.jacket_front)
    _set("button_count", patch.button_count)
    _set("lapel_style", patch.lapel_style)
    _set("lapel_roll", patch.lapel_roll)
    _set("shoulder_padding", patch.shoulder_padding)
    _set("trouser_front", patch.trouser_front)
    _set("neckwear", patch.neckwear)
    _set("notes_normalized", patch.notes_normalized)

    return updated
