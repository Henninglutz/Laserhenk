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
from models.fabric import SelectedFabricData

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
        Process design preferences and lead securing with mood board iteration loop.

        Flow:
        1. Collect design preferences
        2. Generate mood board
        3. Wait for user approval or feedback
        4. Iterate up to 7 times based on feedback
        5. After approval: Create CRM lead and schedule appointment
        6. Handoff to LASERHENK

        Returns:
            AgentDecision with next steps
        """
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

        # Check if we have a REAL Pipedrive lead (not provisional HENK1_LEAD or MOCK)
        has_real_crm_lead = (
            state.customer.crm_lead_id
            and not state.customer.crm_lead_id.startswith("HENK1_LEAD")
            and not state.customer.crm_lead_id.startswith("MOCK_CRM")
        )

        # MOOD BOARD ITERATION LOOP (Max 7 iterations)
        # Check if mood board needs to be generated or re-generated
        if not state.image_state.mood_board_approved:
            # Check if we've hit the iteration limit
            if state.image_state.mood_board_iteration_count >= 7:
                logger.warning("[DesignHenk] Max iterations (7) reached for mood board")
                # Force approval and continue
                state.image_state.mood_board_approved = True
                return AgentDecision(
                    next_agent=None,
                    message="Ich verstehe, dass das Moodbild noch nicht perfekt ist. "
                           "Wir haben das Maximum an Iterationen erreicht, aber keine Sorge - "
                           "beim persönlichen Termin können wir alle Details noch genau besprechen!\n\n"
                           "Lass uns jetzt mit der Terminvereinbarung fortfahren.",
                    action=None,
                    should_continue=False,
                )

            # Generate or re-generate mood board
            if not state.mood_image_url or state.image_state.mood_board_feedback:
                logger.info(f"[DesignHenk] Generating mood board (iteration {state.image_state.mood_board_iteration_count + 1}/7)")

                # Increment iteration counter
                state.image_state.mood_board_iteration_count += 1

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

                # Include user feedback in prompt if available
                if state.image_state.mood_board_feedback:
                    logger.info(f"[DesignHenk] Incorporating user feedback: {state.image_state.mood_board_feedback}")

                    # CRITICAL FIX: Parse feedback and update design_preferences
                    updated_prefs = self._parse_feedback_and_update_preferences(
                        state.image_state.mood_board_feedback,
                        design_prefs
                    )
                    design_prefs.update(updated_prefs)

                    # Also update the session state with parsed preferences
                    for key, value in updated_prefs.items():
                        setattr(state.design_preferences, key, value)

                    # Add feedback to style keywords for additional context
                    style_keywords.append(f"User feedback: {state.image_state.mood_board_feedback}")
                    # Clear feedback after incorporating
                    state.image_state.mood_board_feedback = None

                iteration_msg = f"(Iteration {state.image_state.mood_board_iteration_count}/7)" if state.image_state.mood_board_iteration_count > 1 else ""

                return AgentDecision(
                    next_agent=None,
                    message=f"Generiere Ihr Outfit-Moodbild {iteration_msg}...",
                    action="dalle_tool",
                    action_params={
                        "prompt_type": "outfit_visualization",
                        "fabric_data": fabric_data.model_dump(exclude_none=True),
                        "design_preferences": design_prefs,
                        "style_keywords": style_keywords,
                        "session_id": state.session_id,
                    },
                    should_continue=True,
                )

            # Mood board generated, waiting for user approval
            if state.mood_image_url and not state.image_state.mood_board_approved:
                iterations_left = 7 - state.image_state.mood_board_iteration_count
                return AgentDecision(
                    next_agent=None,
                    message=f"Hier ist Ihr Moodbild für den maßgeschneiderten Anzug! 👔\n\n"
                           f"**Gefällt Ihnen die Richtung?**\n\n"
                           f"✅ Wenn ja, sagen Sie 'Ja', 'Genehmigt' oder 'Perfekt'\n"
                           f"🔄 Wenn Sie Änderungen wünschen, beschreiben Sie einfach, was anders sein soll\n\n"
                           f"Sie können noch bis zu {iterations_left} Änderungen vornehmen.",
                    action=None,
                    should_continue=False,
                )

        # MOOD BOARD APPROVED - Proceed to CRM lead creation
        if state.image_state.mood_board_approved and not has_real_crm_lead:
            logger.info("[DesignHenk] Mood board approved, creating CRM lead")

            # Mark approved image in design preferences
            if state.mood_image_url:
                state.design_preferences.approved_image = state.mood_image_url

            return AgentDecision(
                next_agent=None,
                message="Perfekt! Ich sichere jetzt Ihre Daten und bereite die Terminvereinbarung vor...",
                action="crm_create_lead",
                action_params={
                    "session_id": state.session_id,
                    "customer_name": state.customer.name or "Interessent",
                    "customer_email": state.customer.email or "",
                    "customer_phone": state.customer.phone or "",
                    "mood_image_url": state.mood_image_url,
                },
                should_continue=True,
            )

        # Design phase complete → hand back to supervisor
        # Only proceed if we have a REAL Pipedrive lead
        if has_real_crm_lead:
            return AgentDecision(
                next_agent=None,
                message="✅ Design-Phase abgeschlossen!\n\n"
                       "Als nächstes vereinbaren wir einen Termin mit Henning für die Maßerfassung. "
                       "Bevorzugen Sie einen Termin bei Ihnen zu Hause oder im Büro?",
                action="complete_design_phase",
                should_continue=False,
            )

        # Fallback
        return AgentDecision(
            next_agent=None,
            message="Design phase in progress...",
            action=None,
            should_continue=False,
        )

    def _extract_fabric_data(self, state: SessionState) -> SelectedFabricData:
        """
        Extrahiere Stoffdaten aus HENK1 Payload oder RAG Context als Structured Output.

        Args:
            state: Session State

        Returns:
            SelectedFabricData - Structured fabric data for DALL-E
        """
        # Priority 1: Use favorite_fabric (user's selection)
        if state.favorite_fabric:
            fabric = state.favorite_fabric
            logger.info(f"[DesignHenkAgent] Using favorite_fabric: {fabric.get('fabric_code')}")
            return SelectedFabricData(
                fabric_code=fabric.get("fabric_code"),
                color=fabric.get("color"),
                pattern=fabric.get("pattern"),
                composition=fabric.get("composition"),
                texture=fabric.get("texture"),
                supplier=fabric.get("supplier"),
                image_url=fabric.get("url"),  # ← WICHTIG: Stoffbild URL für Composite
            )

        # Priority 2: Extract from shown_fabric_images (first shown fabric)
        if state.shown_fabric_images and len(state.shown_fabric_images) > 0:
            fabric = state.shown_fabric_images[0]
            logger.info(f"[DesignHenkAgent] Using first shown fabric: {fabric.get('fabric_code')}")
            return SelectedFabricData(
                fabric_code=fabric.get("fabric_code"),
                color=fabric.get("color"),
                pattern=fabric.get("pattern"),
                composition=fabric.get("composition"),
                texture=fabric.get("texture"),
                supplier=fabric.get("supplier"),
                image_url=fabric.get("url"),  # ← WICHTIG: Stoffbild URL für Composite
            )

        # Priority 3: Extract from RAG context
        if state.rag_context and isinstance(state.rag_context, dict) and "fabrics" in state.rag_context:
            fabrics = state.rag_context["fabrics"]
            if fabrics and len(fabrics) > 0:
                main_fabric = fabrics[0]
                # Try to get image URL from various possible keys
                image_url = main_fabric.get("image_url") or main_fabric.get("url")
                if not image_url:
                    # Try local_image_paths
                    local_paths = main_fabric.get("local_image_paths", [])
                    if local_paths:
                        image_url = local_paths[0]

                logger.info(f"[DesignHenkAgent] Using RAG context fabric: {main_fabric.get('fabric_code')}, image_url={image_url}")
                return SelectedFabricData(
                    fabric_code=main_fabric.get("fabric_code"),
                    color=main_fabric.get("color"),
                    pattern=main_fabric.get("pattern"),
                    composition=main_fabric.get("composition"),
                    texture=main_fabric.get("texture"),
                    supplier=main_fabric.get("supplier"),
                    image_url=image_url,  # ← WICHTIG: Stoffbild URL für Composite
                )

        # Fallback: Empty SelectedFabricData
        logger.warning("[DesignHenkAgent] No fabric data found, returning empty SelectedFabricData")
        return SelectedFabricData()

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

    def _parse_feedback_and_update_preferences(
        self, feedback: str, current_prefs: dict
    ) -> dict:
        """
        Parse user feedback and extract design preference changes.

        Args:
            feedback: User feedback text
            current_prefs: Current design preferences dict

        Returns:
            Dict with updated preference values
        """
        feedback_lower = feedback.lower()
        updates = {}

        # Parse lapel/revers type (RAG Spezifikationen)
        if any(word in feedback_lower for word in ["spitzfacon", "spitz facon"]):
            updates["revers_type"] = "Spitzfacon"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Spitzfacon")
        elif any(word in feedback_lower for word in ["fallendes facon", "fallend facon", "falling lapel"]):
            updates["revers_type"] = "fallendes Facon"
            logger.info("[DesignHenk] Parsed feedback: revers_type = fallendes Facon")
        elif any(word in feedback_lower for word in ["stehkragen", "stand collar", "mandarin"]):
            updates["revers_type"] = "Stehkragen"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Stehkragen")
        elif any(word in feedback_lower for word in ["ohne revers", "no lapel", "kein revers"]):
            updates["revers_type"] = "Ohne Revers"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Ohne Revers")
        elif any(word in feedback_lower for word in ["schalkragen", "shawl collar", "schal"]):
            updates["revers_type"] = "Schalkragen"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Schalkragen")
        elif any(word in feedback_lower for word in ["dinner jacket", "smoking", "tuxedo"]):
            updates["revers_type"] = "Dinner Jacket"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Dinner Jacket")
        elif any(word in feedback_lower for word in ["normales revers", "normal lapel", "klassisches revers", "stegrevers"]):
            updates["revers_type"] = "Stegrevers"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Stegrevers")
        elif any(word in feedback_lower for word in ["spitzrevers", "peak lapel"]):
            updates["revers_type"] = "Spitzrevers"
            logger.info("[DesignHenk] Parsed feedback: revers_type = Spitzrevers")

        # Parse shoulder padding
        if any(word in feedback_lower for word in ["keine schulter", "no shoulder", "ohne polster", "ungepolstert"]):
            updates["shoulder_padding"] = "keine"
            logger.info("[DesignHenk] Parsed feedback: shoulder_padding = keine")
        elif any(word in feedback_lower for word in ["leichte schulter", "light shoulder", "wenig polster"]):
            updates["shoulder_padding"] = "leicht"
            logger.info("[DesignHenk] Parsed feedback: shoulder_padding = leicht")
        elif any(word in feedback_lower for word in ["mittlere schulter", "medium shoulder", "mittel"]):
            updates["shoulder_padding"] = "mittel"
            logger.info("[DesignHenk] Parsed feedback: shoulder_padding = mittel")
        elif any(word in feedback_lower for word in ["starke schulter", "strong shoulder", "stark gepolstert"]):
            updates["shoulder_padding"] = "stark"
            logger.info("[DesignHenk] Parsed feedback: shoulder_padding = stark")

        # Parse waistband type
        if any(word in feedback_lower for word in ["bundfalte", "pleated", "mit falte", "falten"]):
            updates["waistband_type"] = "bundfalte"
            logger.info("[DesignHenk] Parsed feedback: waistband_type = bundfalte")
        elif any(word in feedback_lower for word in ["glatt", "flat front", "ohne falte", "keine falte"]):
            updates["waistband_type"] = "glatt"
            logger.info("[DesignHenk] Parsed feedback: waistband_type = glatt")

        # Log if no updates were parsed
        if not updates:
            logger.info(f"[DesignHenk] No specific design preferences parsed from feedback: {feedback}")

        return updates
