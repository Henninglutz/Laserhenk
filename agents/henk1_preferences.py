"""LLM-gestützte Intent-Extraktion für HENK1."""

from dataclasses import dataclass
from typing import Iterable


INTENT_EXTRACTION_PROMPT = """
Analysiere die Nachricht und gib kompaktes JSON zurück:
{
  "wants_fabrics": bool,   # möchte Stoffoptionen sehen?
  "lead_ready": bool,      # klarer Kauf- / Terminwunsch vorhanden?
  "colors": ["Grey", ...],
  "patterns": ["Check", ...]
}
Nutze Kontext aus dem Verlauf, halte dich kurz und wähle nur eindeutige Farben/Muster.
"""


@dataclass
class IntentAnalysis:
    """Struktur für Intent- und Kriterien-Erkennung."""

    wants_fabrics: bool
    search_criteria: dict
    lead_ready: bool = False


def fallback_intent_analysis(user_input: str, history: Iterable[dict]) -> IntentAnalysis:
    """Regelbasierter Fallback ohne LLM-Abhängigkeit."""

    user_input_lower = user_input.lower()

    fabric_keywords = [
        "stoff",
        "stoffe",
        "zeigen",
        "auswahl",
        "empfehl",
        "option",
        "material",
        "sehen",
    ]

    color_keywords = {
        "blau": "Blue",
        "grau": "Grey",
        "schwarz": "Black",
        "braun": "Brown",
        "beige": "Beige",
        "grün": "Green",
    }

    pattern_keywords = {
        "uni": "Solid",
        "einfarbig": "Solid",
        "streifen": "Stripes",
        "karo": "Check",
        "fischgrat": "Herringbone",
    }

    wants_fabrics = any(keyword in user_input_lower for keyword in fabric_keywords)

    colors: list[str] = []
    patterns: list[str] = []

    for keyword, color in color_keywords.items():
        if keyword in user_input_lower and color not in colors:
            colors.append(color)

    for keyword, pattern in pattern_keywords.items():
        if keyword in user_input_lower and pattern not in patterns:
            patterns.append(pattern)

    if not colors or not patterns:
        for msg in history or []:
            content = msg.get("content", "").lower()
            for keyword, color in color_keywords.items():
                if keyword in content and color not in colors:
                    colors.append(color)
            for keyword, pattern in pattern_keywords.items():
                if keyword in content and pattern not in patterns:
                    patterns.append(pattern)

    lead_ready = wants_fabrics and len(list(history or [])) >= 4

    return IntentAnalysis(
        wants_fabrics=wants_fabrics,
        lead_ready=lead_ready,
        search_criteria={"query": user_input, "colors": colors, "patterns": patterns},
    )
