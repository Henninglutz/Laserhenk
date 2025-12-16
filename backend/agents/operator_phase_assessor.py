"""Phase assessment utilities for routing decisions.

This module replaces the legacy OperatorAgent with a lightweight
rule-based assessor that determines which phase is most appropriate
based on the current :class:`SessionState` completeness.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from models.customer import SessionState

logger = logging.getLogger(__name__)


class PhaseAssessment(BaseModel):
    """Structured assessment of the session's progress."""

    missing_fields: list[str] = Field(default_factory=list)
    recommended_phase: Literal["henk1", "design_henk", "laserhenk", "end"]
    is_henk1_complete: bool
    is_design_complete: bool
    is_measurements_complete: bool


class PhaseAssessor:
    """Evaluates session completeness across the main phases."""

    HENK1_MANDATORY_FIELDS = ["occasion", "timing", "fabric_color"]

    DESIGN_CORE_FIELDS = [
        "revers_type",
        "shoulder_padding",
        "inner_lining",
        "pocket_style",
        "button_style",
    ]

    MEASUREMENT_CORE_FIELDS = [
        "chest",
        "waist",
        "hip",
        "shoulder_width",
        "sleeve_length",
        "body_length",
        "inseam",
    ]

    def assess(self, state: SessionState) -> PhaseAssessment:
        """Return a structured assessment for routing decisions."""

        henk1_missing = self._missing_henk1_fields(state)
        design_missing = self._missing_design_fields(state)
        measurements_missing = self._missing_measurement_fields(state)

        is_henk1_complete = not henk1_missing
        is_design_complete = is_henk1_complete and not design_missing
        is_measurements_complete = is_design_complete and not measurements_missing

        if not is_henk1_complete:
            recommended_phase: Literal["henk1", "design_henk", "laserhenk", "end"] = "henk1"
        elif not is_design_complete:
            recommended_phase = "design_henk"
        elif not is_measurements_complete:
            recommended_phase = "laserhenk"
        else:
            recommended_phase = "end"

        missing_fields = henk1_missing + design_missing + measurements_missing

        assessment = PhaseAssessment(
            missing_fields=missing_fields,
            recommended_phase=recommended_phase,
            is_henk1_complete=is_henk1_complete,
            is_design_complete=is_design_complete,
            is_measurements_complete=is_measurements_complete,
        )

        logger.info(
            "[PhaseAssessor] missing_fields=%s | recommended_phase=%s",
            assessment.missing_fields,
            assessment.recommended_phase,
        )

        return assessment

    def _missing_henk1_fields(self, state: SessionState) -> list[str]:
        occasion = self._get_occasion(state)
        timing = self._get_timing(state)
        fabric_color = self._get_fabric_color(state)

        missing = []
        if not occasion:
            missing.append("occasion")
        if not timing:
            missing.append("timing")
        if not fabric_color:
            missing.append("fabric_color")
        return missing

    def _missing_design_fields(self, state: SessionState) -> list[str]:
        missing = []

        handoff = getattr(state, "handoffs", {}) or {}
        design_payload = handoff.get("laserhenk") or getattr(state, "design_to_laser_payload", {}) or {}

        design_prefs = state.design_preferences

        for field in self.DESIGN_CORE_FIELDS:
            if design_payload.get(field):
                continue
            if getattr(design_prefs, field, None):
                continue
            missing.append(field)

        preferred_colors = getattr(design_prefs, "preferred_colors", None)
        if preferred_colors is None or len(preferred_colors) == 0:
            missing.append("fabric_color")

        return missing

    def _missing_measurement_fields(self, state: SessionState) -> list[str]:
        measurements = state.measurements
        if not measurements:
            return self.MEASUREMENT_CORE_FIELDS.copy()

        missing = []
        for field in self.MEASUREMENT_CORE_FIELDS:
            if getattr(measurements, field, None) is None:
                missing.append(field)
        return missing

    def _get_occasion(self, state: SessionState) -> str | None:
        customer = state.customer
        handoff = getattr(state, "handoffs", {}) or {}
        henk_payload = handoff.get("design_henk") or getattr(state, "henk1_to_design_payload", {}) or {}

        occasion = getattr(customer, "occasion", None) or getattr(customer, "event_type", None)
        if occasion:
            return str(occasion)

        occasion = henk_payload.get("occasion")
        if occasion:
            return str(getattr(occasion, "value", occasion))
        return None

    def _get_timing(self, state: SessionState) -> str | None:
        customer = state.customer
        handoff = getattr(state, "handoffs", {}) or {}
        henk_payload = handoff.get("design_henk") or getattr(state, "henk1_to_design_payload", {}) or {}

        return (
            getattr(customer, "event_date", None)
            or getattr(customer, "deadline", None)
            or henk_payload.get("timing")
        )

    def _get_fabric_color(self, state: SessionState) -> str | None:
        design_prefs = state.design_preferences
        handoff = getattr(state, "handoffs", {}) or {}
        henk_payload = handoff.get("design_henk") or getattr(state, "henk1_to_design_payload", {}) or {}

        preferred_colors = getattr(design_prefs, "preferred_colors", None)
        if preferred_colors:
            return ", ".join(preferred_colors)

        colors = henk_payload.get("colors")
        if colors:
            if isinstance(colors, list):
                return ", ".join(str(c) for c in colors)
            return str(colors)

        return getattr(design_prefs, "lining_color", None)
