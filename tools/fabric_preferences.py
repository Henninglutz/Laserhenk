"""Hilfsfunktionen für Stoffsuche-Präferenzen."""

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from models.customer import SessionState
from models.fabric import FabricSearchCriteria

logger = logging.getLogger(__name__)

GERMAN_COLOR_MAP: Dict[str, str] = {
    "rot": "red",
    "weinrot": "burgundy",
    "bordeaux": "burgundy",
    "burgunder": "burgundy",
    "dunkelblau": "dark blue",
    "hellblau": "light blue",
    "blau": "blue",
    "marine": "navy",
    "navy": "navy",
    "dunkelgrau": "dark grey",
    "hellgrau": "light grey",
    "grau": "grey",
    "schwarz": "black",
    "dunkelbraun": "dark brown",
    "hellbraun": "light brown",
    "braun": "brown",
    "beige": "beige",
    "dunkelgrün": "dark green",
    "hellgrün": "light green",
    "grün": "green",
    "olive": "olive",
}

NEGATION_WORDS = ["nicht", "ohne", "kein", "keine", "keinen", "keiner", "keines", "keinem"]

LIGHT_KEYWORDS = ["leicht", "luftig", "sommer", "sommerlich", "leichter"]
LIGHTWEIGHT_THRESHOLD = 250

MATERIAL_KEYWORDS = {
    "leinen": "linen",
    "linen": "linen",
    "baumwolle": "cotton",
    "cotton": "cotton",
    "chino": "cotton",
}


def _normalize_session_state(session_state: Optional[SessionState | dict]) -> Optional[SessionState]:
    if isinstance(session_state, dict):
        return SessionState(**session_state)
    return session_state


def _extract_colors(query_lower: str) -> Tuple[list[str], list[str]]:
    excluded_colors: list[str] = []
    extracted_colors: list[str] = []
    matched_positions: list[tuple[int, int]] = []

    def _is_negated(color_word: str) -> bool:
        pattern = rf"(?:{'|'.join(NEGATION_WORDS)})(?:\s+\w+){{0,2}}\s+{re.escape(color_word)}\w*"
        return re.search(pattern, query_lower) is not None

    for german, english in GERMAN_COLOR_MAP.items():
        negated = _is_negated(german) or _is_negated(english)
        if negated:
            excluded_colors.append(english)

        for match in re.finditer(rf"\b{re.escape(german)}\w*\b", query_lower):
            pos = match.start()
            overlaps = any(not (pos + len(german) <= start or pos >= end) for start, end in matched_positions)
            if not overlaps and not negated:
                extracted_colors.append(english)
                matched_positions.append((pos, pos + len(german)))

    return extracted_colors, excluded_colors


def _merge_colors(explicit_colors: Sequence[str], extracted_colors: Sequence[str]) -> list[str]:
    if explicit_colors and extracted_colors:
        merged = list(dict.fromkeys([*explicit_colors, *extracted_colors]))
        logger.info(f"[FabricPrefs] Merged colors from params/query: {merged}")
        return merged
    if extracted_colors:
        logger.info(f"[FabricPrefs] Extracted colors from query: {list(extracted_colors)}")
        return list(extracted_colors)
    return list(explicit_colors)


def _detect_lightweight_preference(query_lower: str, weight_max: Optional[int]) -> Optional[int]:
    if weight_max:
        return weight_max
    if any(keyword in query_lower for keyword in LIGHT_KEYWORDS):
        logger.info("[FabricPrefs] Detected lightweight preference -> weight_max=250")
        return LIGHTWEIGHT_THRESHOLD
    return None


def _detect_materials(query_lower: str, preferred_materials: Optional[Iterable[str]]) -> Optional[list[str]]:
    if preferred_materials:
        return list(preferred_materials)

    materials_detected = []
    for keyword, material in MATERIAL_KEYWORDS.items():
        if keyword in query_lower:
            materials_detected.append(material)

    if materials_detected:
        logger.info(f"[FabricPrefs] Detected material preferences: {materials_detected}")
        return materials_detected
    return None


def build_fabric_search_criteria(
    query: str,
    params: Dict[str, Any],
    session_state: Optional[SessionState | dict],
) -> tuple[FabricSearchCriteria, Optional[SessionState], list[str], list[str]]:
    """Erstellt eine FabricSearchCriteria-Instanz aus Query + Parametern.

    Returns:
        criteria, aktualisierte Session, ausgeschlossene Farben, aktive Filter-Texte
    """

    normalized_state = _normalize_session_state(session_state)
    raw_colors = params.get("colors") or params.get("color") or []
    if isinstance(raw_colors, str):
        colors = [raw_colors]
    else:
        colors = raw_colors or []
    colors = [c.strip().lower() for c in colors if c]

    raw_patterns = params.get("patterns", []) or []
    patterns = [raw_patterns] if isinstance(raw_patterns, str) else raw_patterns
    weight_max = params.get("weight_max")
    preferred_materials = params.get("preferred_materials") or params.get("materials")

    query_lower = query.lower() if query else ""
    extracted_colors: list[str] = []
    excluded_colors: list[str] = []

    if query_lower:
        extracted_colors, excluded_colors = _extract_colors(query_lower)
        weight_max = _detect_lightweight_preference(query_lower, weight_max)
        preferred_materials = _detect_materials(query_lower, preferred_materials)

    colors = _merge_colors(colors, extracted_colors)
    if excluded_colors:
        excluded_lower = {c.lower() for c in excluded_colors}
        colors = [c for c in colors if c.lower() not in excluded_lower]

    if not colors and normalized_state and normalized_state.design_preferences:
        stored_colors = normalized_state.design_preferences.preferred_colors
        if stored_colors:
            colors = stored_colors
            logger.info(f"[FabricPrefs] Using stored color preferences: {colors}")
        else:
            logger.info("[FabricPrefs] No stored color preferences found in session")

    if colors and normalized_state:
        if not normalized_state.design_preferences.preferred_colors:
            normalized_state.design_preferences.preferred_colors = colors
            logger.info(f"[FabricPrefs] Stored NEW color preferences in session: {colors}")
        else:
            # Merge with existing colors (keep both)
            existing = normalized_state.design_preferences.preferred_colors
            merged = list(dict.fromkeys([*existing, *colors]))  # Remove duplicates, preserve order
            if merged != existing:
                normalized_state.design_preferences.preferred_colors = merged
                logger.info(f"[FabricPrefs] MERGED color preferences: {existing} + {colors} = {merged}")
            else:
                logger.info(f"[FabricPrefs] Color preferences unchanged: {colors}")

    criteria = FabricSearchCriteria(
        colors=colors,
        patterns=patterns,
        preferred_materials=preferred_materials or None,
        weight_max=weight_max,
        limit=params.get("limit", 10),
    )

    filters: list[str] = []
    if colors:
        filters.append(f"Farben: {', '.join(colors)}")
    if preferred_materials:
        filters.append(f"Materialien: {', '.join(preferred_materials)}")
    if weight_max:
        filters.append(f"≤ {weight_max}g/m²")

    return criteria, normalized_state, excluded_colors, filters
