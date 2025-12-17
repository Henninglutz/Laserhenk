"""Design HENK Agent - Design Präferenzen & Leadsicherung.

AGENT BESCHREIBUNG (für LLM als System Prompt):
------------------------------------------------
Du bist Design HENK, der Design-Spezialist für maßgeschneiderte Herrenanzüge.
Deine Aufgaben:

1. **Design-Details sammeln**:
   - Revers-Typ (Spitzrevers, Stegrevers, Schalkragen)
   - Schulterpolsterung (keine, leicht, mittel, stark)
   - Hosenbund-Typ (Bundfalte, glatt, zwei Falten)
   - Innenfutter (Viskose, Seide, Baumwolle)
   - Weitere Präferenzen (Knopfanzahl, Taschenstil, etc.)

2. **DALL-E Visualisierung**:
   - Generiere ein Mood-Image des geplanten Outfits
   - Nutze die Stoffdaten aus HENK1 (Farben, Muster)
   - Kombiniere mit den Design-Details
   - Zeige dem Kunden das Ergebnis
   - Iteriere basierend auf Feedback (bis zu 3 Versuche)

3. **Lead Sicherung (CRM - PIPEDRIVE)**:
   - Erstelle einen Lead im CRM
   - Speichere alle gesammelten Daten
   - Markiere Design-Phase als abgeschlossen

CONDITIONAL EDGES:
------------------
- Nach Design-Details Sammlung → DALL-E Bildgenerierung
- Nach Bild-Generierung → Zeige dem User, warte auf Feedback
- Bei User-Ablehnung → Re-Generate mit angepasstem Prompt
- Bei User-Genehmigung → CRM Lead erstellen
- Nach CRM Lead → Zu LASERHENK oder Operator

STATE ATTRIBUTES:
-----------------
- `state.design_preferences.*` - Design-Details (revers_type, shoulder_padding, etc.)
- `state.mood_image_url` - Generierte Bild-URL
- `state.design_preferences.approved_image` - User-bestätigte Bild-URL
- `state.customer.crm_lead_id` - CRM Lead ID nach Sicherung
- `state.henk1_to_design_payload` - Payload von HENK1 (Budget, Stil, Stoffe)

BEISPIEL-ABLAUF:
----------------
1. User kommt von HENK1 mit Stoffauswahl
2. Frage nach Revers-Präferenz: "Welchen Revers-Stil bevorzugen Sie?"
3. Frage nach Schulterpolsterung: "Wie ausgeprägt soll die Schulter sein?"
4. Sammle weitere Details
5. Generiere Mood-Image: action="generate_image"
6. Zeige Bild: "Hier ist Ihr geplantes Outfit. Gefällt Ihnen die Richtung?"
7. Bei Zustimmung: Erstelle CRM Lead
8. Weiter zu LASERHENK für Finalisierung
"""

import logging
from typing import Optional

from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState

logger = logging.getLogger(__name__)


class DesignHenkAgent(BaseAgent):
    """
    Design HENK (HENK2) - Design & Leadsicherung Agent.

    Aufgaben:
    - RAG Datenbank nutzen für Designoptionen
    - Kundenwünsche abfragen:
      * Reversbreite
      * Schulterpolster
      * Hosenbund
      * Innenfutter
      * weitere Details
    - DALLE Bildgenerierung (Moodbild):
      * Alte Infos (aus RAG/Datenbank)
      * Neue Infos (aus aktueller Session)
    - **LEADSICHERUNG mit CRM (PIPEDRIVE)**
    """

    def __init__(self):
        """Initialize Design HENK Agent."""
        super().__init__("design_henk")

    async def process(self, state: SessionState) -> AgentDecision:
        """
        Process design preferences and lead securing.

        Returns:
            AgentDecision with next steps
        """
        # Hier würde die LLM-Logik für Design-Abfrage stehen
        # Für jetzt: Struktur-Placeholder

        # Check if we need to query RAG for design options
        # DISABLED: Design RAG not implemented yet, skip for now
        # if not state.design_rag_queried:
        #     return AgentDecision(
        #         next_agent="design_henk",
        #         message="Querying RAG for design options",
        #         action="rag_tool",  # FIXED: was "query_rag"
        #         action_params={
        #             "query": "Design options: Revers, Futter, Schulter, Bund"
        #         },
        #         should_continue=True,
        #     )

        # TEMPORARY: Mark as queried to skip infinite loop
        if not state.design_rag_queried:
            state.design_rag_queried = True
            logger.info("[DesignHenk] ⚠️ Design RAG disabled - skipping to preferences collection")

        # Check if design preferences are collected
        preferences_complete = (
            state.design_preferences.revers_type is not None
            and state.design_preferences.shoulder_padding is not None
        )

        if not preferences_complete:
            # TODO: Replace with actual LLM conversation to collect preferences
            # For now: Mock data to prevent infinite loop
            state.design_preferences.revers_type = "Spitzrevers"
            state.design_preferences.shoulder_padding = "mittel"
            state.design_preferences.waistband_type = "bundfalte"

            return AgentDecision(
                next_agent=None,
                message="Perfekt! Lass uns jetzt über die Details deines Anzugs sprechen.\n\n"
                       "Ich würde gerne ein paar Fragen zum Schnitt stellen:\n\n"
                       "1️⃣ **Revers-Stil**: Bevorzugst du klassische Spitzrevers oder moderne Stegrevers?\n"
                       "2️⃣ **Schulterpolster**: Wie ausgeprägt soll die Schulter sein? (keine, leicht, mittel, stark)\n"
                       "3️⃣ **Hosenbund**: Mit Bundfalte oder glatt?\n\n"
                       "Sag mir einfach, was dir gefällt!",
                action=None,
                should_continue=False,
            )

        # Generate mood image with DALLE
        if not state.mood_image_url:
            logger.info("[DesignHenkAgent] Triggering DALL-E image generation")

            # Prepare fabric data from HENK1 payload or RAG context
            fabric_data = self._extract_fabric_data(state)

            # Prepare design preferences
            design_prefs = {
                "revers_type": state.design_preferences.revers_type,
                "shoulder_padding": state.design_preferences.shoulder_padding,
                "waistband_type": state.design_preferences.waistband_type,
            }

            # Extract style keywords
            style_keywords = self._extract_style_keywords(state)

            return AgentDecision(
                next_agent=None,
                message="Generiere Ihr Outfit-Moodbild...",
                action="dalle_tool",  # FIXED: was "generate_image", must match TOOL_REGISTRY
                action_params={
                    "prompt_type": "outfit_visualization",
                    "fabric_data": fabric_data,
                    "design_preferences": design_prefs,
                    "style_keywords": style_keywords,
                    "session_id": state.session_id,
                },
                should_continue=True,
            )

        # Mandatory: Leadsicherung mit CRM**
        if not state.customer.crm_lead_id:
            # TODO: Replace with actual CRM API call
            # For now: Mock CRM ID to prevent infinite loop
            state.customer.crm_lead_id = f"MOCK_CRM_{state.session_id[:8]}"

            return AgentDecision(
                next_agent=None,
                message="Lead secured in CRM (mock)",
                action=None,
                should_continue=False,
            )

        # Design phase complete → hand back to supervisor
        return AgentDecision(
            next_agent=None,
            message="Design phase complete, lead secured",
            action="complete_design_phase",
            should_continue=False,
        )

    def _extract_fabric_data(self, state: SessionState) -> dict:
        """
        Extrahiere Stoffdaten aus HENK1 Payload oder RAG Context.

        Args:
            state: Session State

        Returns:
            Fabric data dict mit colors, patterns, etc.
        """
        fabric_data = {}

        # From HENK1 to Design payload
        if state.henk1_to_design_payload:
            payload = state.henk1_to_design_payload
            fabric_data["colors"] = [c.value for c in payload.get("colors", [])]
            fabric_data["patterns"] = [p.value for p in payload.get("patterns", [])]
            fabric_data["season"] = payload.get("season")
            if payload.get("fabric_references"):
                fabric_data["fabric_references"] = payload.get("fabric_references")

        # From RAG context
        elif state.rag_context and isinstance(state.rag_context, dict) and "fabrics" in state.rag_context:
            fabrics = state.rag_context["fabrics"]
            if fabrics and len(fabrics) > 0:
                # Nehme ersten Stoff als Hauptstoff
                main_fabric = fabrics[0]
                fabric_data["colors"] = main_fabric.get("colors", [])
                fabric_data["patterns"] = main_fabric.get("pattern_types", [])
                fabric_data["fabric_code"] = main_fabric.get("fabric_code")
                fabric_data["texture"] = main_fabric.get("texture")
        elif state.rag_context and isinstance(state.rag_context, dict):
            suggestions = state.rag_context.get("fabric_suggestions", [])
            references = [s.get("fabric", {}).get("reference") for s in suggestions if s.get("fabric")]
            if references:
                fabric_data["fabric_references"] = references

        logger.info(f"[DesignHenkAgent] Extracted fabric data: {fabric_data}")
        return fabric_data

    def _extract_style_keywords(self, state: SessionState) -> list[str]:
        """
        Extrahiere Stil-Keywords aus Payload und Preferences.

        Args:
            state: Session State

        Returns:
            Liste von Style Keywords
        """
        keywords = []

        # From HENK1 payload
        if state.henk1_to_design_payload:
            payload = state.henk1_to_design_payload

            # Style
            if "style" in payload:
                style = payload["style"]
                if hasattr(style, "value"):
                    keywords.append(style.value)
                else:
                    keywords.append(str(style))

            # Occasion
            if "occasion" in payload:
                occasion = payload["occasion"]
                if hasattr(occasion, "value"):
                    keywords.append(occasion.value)
                else:
                    keywords.append(str(occasion))

        # From design preferences
        if state.design_preferences.revers_type:
            keywords.append("klassisch" if "spitz" in state.design_preferences.revers_type.lower() else "modern")

        # Fallback keywords
        if not keywords:
            keywords = ["elegant", "maßgeschneidert", "business"]

        logger.info(f"[DesignHenkAgent] Extracted style keywords: {keywords}")
        return keywords
