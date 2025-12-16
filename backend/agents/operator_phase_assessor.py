"""Lightweight phase assessor replacing the legacy operator routing."""

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

    DESIGN_CORE_FIELDS = ["revers_type", "shoulder_padding", "waistband_type"]
    MEASUREMENT_CORE_FIELDS = [
        "shoulder_width",
        "chest",
        "waist",
        "hip",
        "sleeve_length",
        "body_length",
        "inseam",
    ]

    def assess(self, state: SessionState) -> PhaseAssessment:
        """Return a structured assessment for routing decisions."""

        henk1_missing = self._missing_henk1_fields(state)
        design_missing = self._missing_design_fields(state)
        measurements_missing = self._missing_measurement_fields(state)

        # HENK1 is complete if occasion + timing + fabric color are present (timing may be soft).
        is_henk1_complete = not {"occasion", "timing", "fabric_color"} & set(
            henk1_missing
        )
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
        missing: list[str] = []

        if not self._get_occasion(state):
            missing.append("occasion")

        if not self._get_timing(state):
            missing.append("timing")

        if not self._get_fabric_color(state):
            missing.append("fabric_color")

        return missing

    def _missing_design_fields(self, state: SessionState) -> list[str]:
        missing: list[str] = []
        design_prefs = state.design_preferences

        for field in self.DESIGN_CORE_FIELDS:
            if getattr(design_prefs, field, None):
                continue
            handoff_val = self._get_design_handoff_value(state, field)
            if handoff_val:
                continue
            missing.append(field)

        if not self._get_fabric_color(state):
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

    def _get_design_handoff_value(self, state: SessionState, field: str) -> str | None:
        handoff = getattr(state, "handoffs", {}) or {}
        payload = handoff.get("laserhenk") or getattr(state, "design_to_laser_payload", {}) or {}
        raw_val = payload.get(field)
        if raw_val:
            return str(getattr(raw_val, "value", raw_val))
        return None

    def _get_timing(self, state: SessionState) -> str | None:
        handoff = getattr(state, "handoffs", {}) or {}
        payload = handoff.get("design_henk") or getattr(state, "henk1_to_design_payload", {}) or {}

        return (
            getattr(state.customer, "event_date", None)
            or getattr(state.customer, "event_date_hint", None)
            or payload.get("timing")
            or payload.get("deadline")
        )

    def _get_occasion(self, state: SessionState) -> str | None:
        handoff = getattr(state, "handoffs", {}) or {}
        payload = handoff.get("design_henk") or getattr(state, "henk1_to_design_payload", {}) or {}

        if payload.get("occasion"):
            return str(payload["occasion"])

        # Lightweight keyword-based extraction from recent conversation
        convo = " ".join(
            msg.get("content", "").lower()
            for msg in state.conversation_history[-10:]
            if isinstance(msg, dict)
        )
        occasion_keywords = {
            "hochzeit": "hochzeit",
            "wedding": "wedding",
            "business": "business",
            "gala": "gala",
            "party": "party",
            "feier": "feier",
            "formal": "formal",
            "casual": "casual",
        }

        for keyword, value in occasion_keywords.items():
            if keyword in convo:
                return value

        return None

    def _get_fabric_color(self, state: SessionState) -> str | None:
        prefs = state.design_preferences
        handoff = getattr(state, "handoffs", {}) or {}
        henk_payload = handoff.get("design_henk") or getattr(state, "henk1_to_design_payload", {}) or {}

        preferred_colors = getattr(prefs, "preferred_colors", None)
        if preferred_colors:
            return ", ".join(str(c) for c in preferred_colors)

        lining_color = getattr(prefs, "lining_color", None)
        if lining_color:
            return str(lining_color)

        favorite_fabric = getattr(state, "favorite_fabric", None) or {}
        if favorite_fabric.get("color"):
            return str(favorite_fabric["color"])

        payload_colors = henk_payload.get("colors") or henk_payload.get("color")
        if payload_colors:
            if isinstance(payload_colors, list):
                return ", ".join(str(c) for c in payload_colors)
            return str(payload_colors)

        return None
