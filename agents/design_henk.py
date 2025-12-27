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

import json
import logging
import os
from typing import Optional

from agents.base import AgentDecision, BaseAgent
from agents.prompt_loader import IMAGE_SYSTEM_CONTRACT
from agents.design_patch_agent import DesignPatchAgent
from models.customer import SessionState
from models.fabric import SelectedFabricData
from models.patches import apply_design_preferences_patch

try:
    from openai import AsyncOpenAI
except ModuleNotFoundError:
    AsyncOpenAI = None

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

        # Initialize OpenAI client for LLM conversations
        self.client = None
        if AsyncOpenAI is not None and os.environ.get("OPENAI_API_KEY"):
            try:
                self.client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                logger.info("[DesignHenk] ✅ OpenAI client initialized")
            except Exception as exc:
                logger.warning("[DesignHenk] OpenAI client initialization failed: %s", exc)

        # Load style catalog for RAG knowledge
        self.style_catalog = self._load_style_catalog()
        if self.style_catalog:
            dress_codes = list(self.style_catalog.get("dress_codes", {}).keys())
            logger.info("[DesignHenk] ✅ Style catalog loaded: %d dress codes", len(dress_codes))
        else:
            logger.warning("[DesignHenk] ⚠️ Style catalog not loaded")

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

        if state.image_generation_failed:
            error_hint = f" Grund: {state.last_tool_error}" if state.last_tool_error else ""
            return AgentDecision(
                next_agent=None,
                message=(
                    "Die Bildgenerierung ist leider fehlgeschlagen."
                    f"{error_hint}\n"
                    "Ich kann dir stattdessen sofort eine textbasierte Outfitbeschreibung senden oder wir versuchen es später"
                    " erneut, sobald die Konfiguration passt."
                ),
                action=None,
                should_continue=False,
            )

        # Check if design preferences are collected
        preferences_complete = (
            state.design_preferences.revers_type is not None
            and state.design_preferences.shoulder_padding is not None
        )

        if not preferences_complete:
            # Use LLM for flexible conversation about design preferences
            llm_response = await self._process_with_llm(
                state,
                context_message="Der Kunde hat einen Stoff ausgewählt. Frage jetzt nach Design-Präferenzen (Revers, Schultern, Hosenbund)."
            )

            # Set default values to prevent infinite loop (will be overridden by user feedback)
            state.design_preferences.revers_type = "Spitzrevers"
            state.design_preferences.shoulder_padding = "mittel"
            state.design_preferences.waistband_type = "bundfalte"

            return AgentDecision(
                next_agent=None,
                message=llm_response,
                action=None,
                should_continue=False,
            )

        # Check if we have a CRM lead (real Pipedrive OR MOCK for development)
        # CRITICAL: MOCK leads ARE acceptable to prevent infinite loop
        # Only exclude provisional HENK1 leads (created before mood board approval)
        has_crm_lead = (
            state.customer.crm_lead_id
            and not state.customer.crm_lead_id.startswith("HENK1_LEAD")  # Only exclude provisional HENK1 leads
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
                    "wants_vest": state.design_preferences.wants_vest,
                    "trouser_color": state.design_preferences.trouser_color,
                    "preferred_material": state.design_preferences.preferred_material,
                    "requested_fabric_code": state.design_preferences.requested_fabric_code,
                }

                # Extract style keywords
                style_keywords = self._extract_style_keywords(state)

                # Include user feedback in prompt if available
                if state.image_state.mood_board_feedback:
                    logger.info(f"[DesignHenk] Incorporating user feedback: {state.image_state.mood_board_feedback}")

                    # Extract structured patches from feedback
                    patch_agent = DesignPatchAgent()
                    decision = await patch_agent.extract_patch_decision(
                        user_message=state.image_state.mood_board_feedback,
                        context="Designpräferenzen Update",
                    )

                    logger.info(
                        "[DesignHenk] PatchDecision for feedback '%s': %s",
                        state.image_state.mood_board_feedback,
                        decision.model_dump_json(),
                    )

                    # Apply patches to design preferences
                    if decision.confidence > 0.5:
                        applied_fields = []
                        updated_preferences = apply_design_preferences_patch(
                            state.design_preferences, decision.patch
                        )

                        for field_name in updated_preferences.model_fields:
                            new_value = getattr(updated_preferences, field_name)
                            old_value = getattr(state.design_preferences, field_name)
                            if new_value != old_value:
                                applied_fields.append(field_name)
                                logger.info(
                                    "[DesignHenk] 🔄 Updated %s: %s → %s",
                                    field_name,
                                    old_value,
                                    new_value,
                                )

                        state.design_preferences = updated_preferences

                        # Update wants_vest in root state
                        if decision.patch.wants_vest is not None:
                            state.wants_vest = decision.patch.wants_vest
                            applied_fields.append("wants_vest")
                            logger.info(
                                "[DesignHenk] 🔄 Updated wants_vest: %s",
                                state.wants_vest,
                            )

                        # Handle fabric switching if requested
                        if decision.patch.requested_fabric_code:
                            requested_code = decision.patch.requested_fabric_code
                            logger.info(
                                "[DesignHenk] 🎨 User requested fabric change to: %s",
                                requested_code,
                            )

                            # Search for fabric in shown_fabric_images
                            fabric_found = False
                            if state.shown_fabric_images:
                                for fabric in state.shown_fabric_images:
                                    if fabric.get("fabric_code") == requested_code:
                                        # Update favorite_fabric to new selection
                                        old_fabric = state.favorite_fabric.get("fabric_code") if state.favorite_fabric else None
                                        state.favorite_fabric = fabric
                                        fabric_found = True
                                        applied_fields.append("requested_fabric_code")
                                        logger.info(
                                            "[DesignHenk] ✅ Switched fabric: %s → %s",
                                            old_fabric,
                                            requested_code,
                                        )
                                        break

                            if not fabric_found:
                                logger.warning(
                                    "[DesignHenk] ⚠️ Requested fabric %s not found in shown_fabric_images",
                                    requested_code,
                                )

                        logger.info(
                            "[DesignHenk] ✅ Applied %d fields from PatchDecision: %s",
                            len(applied_fields),
                            applied_fields,
                        )

                        # Update design_prefs dict for DALLE
                        design_prefs.update(
                            {
                                "revers_type": state.design_preferences.revers_type,
                                "shoulder_padding": state.design_preferences.shoulder_padding,
                                "waistband_type": state.design_preferences.waistband_type,
                                "jacket_front": state.design_preferences.jacket_front,
                                "lapel_style": state.design_preferences.lapel_style,
                                "lapel_roll": state.design_preferences.lapel_roll,
                                "trouser_front": state.design_preferences.trouser_front,
                                "notes_normalized": state.design_preferences.notes_normalized,
                                "wants_vest": state.design_preferences.wants_vest,
                                "trouser_color": state.design_preferences.trouser_color,
                                "preferred_material": state.design_preferences.preferred_material,
                                "requested_fabric_code": state.design_preferences.requested_fabric_code,
                            }
                        )
                    else:
                        logger.warning(
                            "[DesignHenk] ⚠️ Low confidence (%.2f), not applying patches",
                            decision.confidence,
                        )

                    # Extract style keywords from feedback using LLM
                    feedback_keywords = await self._extract_style_keywords_from_feedback(
                        state.image_state.mood_board_feedback
                    )

                    # Merge with existing style keywords
                    if feedback_keywords:
                        style_keywords.extend(feedback_keywords)
                        logger.info(
                            "[DesignHenk] 🎨 Merged style keywords: %s",
                            style_keywords,
                        )

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

                # Use LLM for flexible, charming mood board presentation
                llm_response = await self._process_with_llm(
                    state,
                    context_message=f"Das Moodbild wurde generiert. Präsentiere es dem Kunden charmant und frage, ob es ihm gefällt. Erwähne, dass noch {iterations_left} Änderungen möglich sind."
                )

                return AgentDecision(
                    next_agent=None,
                    message=llm_response,
                    action=None,
                    should_continue=False,
                )

        # MOOD BOARD APPROVED - Check email before CRM lead creation
        if state.image_state.mood_board_approved and not has_crm_lead:
            logger.info("[DesignHenk] Mood board approved")

            # Mark approved image in design preferences
            if state.mood_image_url:
                state.design_preferences.approved_image = state.mood_image_url

            # CRITICAL: Email is mandatory for CRM lead creation
            if not state.customer.email:
                logger.info("[DesignHenk] Email missing, requesting from user")

                # Use LLM for charming email request
                llm_response = await self._process_with_llm(
                    state,
                    context_message="Das Moodbild wurde genehmigt! Gratuliere dem Kunden und frage charmant nach seiner E-Mail-Adresse, um den Termin vorzubereiten."
                )

                return AgentDecision(
                    next_agent=None,
                    message=llm_response,
                    action=None,
                    should_continue=False,
                )

            # Email vorhanden, proceed to CRM lead creation
            logger.info("[DesignHenk] Email present, creating CRM lead")
            return AgentDecision(
                next_agent=None,
                message="Perfekt! Ich sichere jetzt Ihre Daten und bereite die Terminvereinbarung vor...",
                action="crm_create_lead",
                action_params={
                    "session_id": state.session_id,
                    "customer_name": state.customer.name or "Interessent",
                    "customer_email": state.customer.email,
                    "customer_phone": state.customer.phone or "",
                    "mood_image_url": state.mood_image_url,
                },
                should_continue=True,
            )

        # Design phase complete → hand back to supervisor
        # Only proceed if we have a CRM lead (real or mock)
        if has_crm_lead:
            # Use LLM for charming phase completion and appointment request
            llm_response = await self._process_with_llm(
                state,
                context_message="Design-Phase erfolgreich abgeschlossen! Gratuliere dem Kunden und frage, ob er den Termin lieber zu Hause oder im Büro haben möchte."
            )

            return AgentDecision(
                next_agent=None,
                message=llm_response,
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

    async def _extract_style_keywords_from_feedback(self, feedback: str) -> list[str]:
        """
        Extract style keywords from raw user feedback using LLM.

        Args:
            feedback: User feedback message

        Returns:
            List of extracted style keywords
        """
        if not feedback or AsyncOpenAI is None or not os.environ.get("OPENAI_API_KEY"):
            return []

        try:
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

            system_prompt = """Extract style keywords from German user feedback for a bespoke suit.

IMPORTANT: Return ONLY a JSON object with a "keywords" array. No explanations.

Examples:
Input: "modern, leicht, italienisch"
Output: {"keywords": ["modern", "light", "italian"]}

Input: "klassischer Schnitt, elegant, business"
Output: {"keywords": ["classic", "elegant", "business"]}

Input: "ohne Futter ohne Polster, aufgesetzte Taschen"
Output: {"keywords": ["unlined", "unpadded", "patch pockets"]}

Extract keywords related to:
- Style (classic, modern, contemporary)
- Construction (lightweight, structured, soft)
- Regional influence (Italian, British, American)
- Occasion (business, formal, casual)
- Design details (patch pockets, unlined, etc.)"""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": feedback}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            data = json.loads(response.choices[0].message.content)
            keywords = data.get("keywords", [])

            logger.info(
                "[DesignHenkAgent] ✅ Extracted %d style keywords from feedback: %s",
                len(keywords),
                keywords,
            )

            return keywords

        except Exception as exc:
            logger.warning(
                "[DesignHenkAgent] Style keyword extraction failed: %s",
                exc,
            )
            return []

    def _get_system_prompt(self, state: SessionState) -> str:
        """Build system prompt for Design Henk based on current context."""
        # Build context information
        fabric_info = ""
        if state.favorite_fabric:
            fabric = state.favorite_fabric
            fabric_info = f"\n- Stoff: {fabric.get('fabric_code')} ({fabric.get('color')}, {fabric.get('pattern')})"

        design_info = ""
        if state.design_preferences:
            prefs = []
            if state.design_preferences.lapel_style:
                prefs.append(f"Revers: {state.design_preferences.lapel_style}")
            if state.design_preferences.shoulder_padding:
                prefs.append(f"Schulter: {state.design_preferences.shoulder_padding}")
            if state.design_preferences.trouser_front:
                prefs.append(f"Hose: {state.design_preferences.trouser_front}")
            if state.wants_vest is not None:
                prefs.append("mit Weste" if state.wants_vest else "ohne Weste")
            if prefs:
                design_info = f"\n- Bisherige Präferenzen: {', '.join(prefs)}"

        iteration_info = ""
        if state.image_state.mood_board_iteration_count > 0:
            iteration_info = f"\n- Moodbild-Iteration: {state.image_state.mood_board_iteration_count}/7"

        # Get style knowledge based on occasion
        occasion = None
        if hasattr(state, 'henk1_to_design_payload') and state.henk1_to_design_payload:
            occasion = state.henk1_to_design_payload.get('occasion')

        style_knowledge = self._get_style_knowledge(occasion)

        return f"""Du bist Design HENK, der kreative Design-Spezialist bei LASERHENK.

Deine Aufgabe - DESIGN-BERATUNG & VISUALISIERUNG:

🎨 DEINE ROLLE:
- Du bist charmant, kreativ und detailversessen
- Du hilfst dem Kunden, seinen perfekten Anzug zu visualisieren
- Du stellst Fragen zu Schnitt-Details (Revers, Schultern, Hose, etc.)
- Du erstellst Moodbilder basierend auf seinen Wünschen
- Du iterierst bis der Kunde zufrieden ist (max. 7 Iterationen)

📊 AKTUELLER STATUS:{fabric_info}{design_info}{iteration_info}
{style_knowledge}

💬 GESPRÄCHSFÜHRUNG:
- Sei herzlich, persönlich und begeisternd
- Nutze lockere Sprache ("du", emoji 🎩✨)
- Erkläre Design-Optionen verständlich
- Reagiere auf ALLE Kundenfragen (Preis, Lieferzeit, Details, etc.)
- Gehe auf Feedback ein und passe das Moodbild an

🎯 DESIGN-DETAILS ZU KLÄREN:
1. Revers-Stil (Spitzrevers, Stegrevers, Schalkragen)
2. Schulterpolsterung (keine, leicht, mittel, stark)
3. Hosenbund (Bundfalte, glatt)
4. Weste (ja/nein)
5. Weitere Präferenzen (Knopfanzahl, Taschenstil)

📸 MOODBILD-ITERATION:
- Nach jedem Feedback: Erkläre kurz, was du änderst
- Sei positiv und motivierend
- Zeige Verständnis für Kundenwünsche
- Wenn zufrieden → Lead sichern & Termin vereinbaren

💰 PREISE (wenn gefragt):
- Einstieg: ab 899€ (2-Teiler, Standardstoffe)
- Premium: 1.200-2.500€ (hochwertige Stoffe, mehr Details)
- Luxus: 2.500€+ (exklusive Stoffe, alle Details)
- Hinweis: "Genauer Preis wird im persönlichen Termin besprochen"

⏱️ LIEFERZEIT (wenn gefragt):
- Standardproduktion: 4-6 Wochen
- Express: 2-3 Wochen (gegen Aufpreis)
- Bei Termindruck: "Wir finden eine Lösung!"

Wichtig: Antworte IMMER auf Deutsch, kurz, charmant und hilfreich!

{IMAGE_SYSTEM_CONTRACT}"""

    async def _process_with_llm(
        self, state: SessionState, context_message: str = ""
    ) -> str:
        """
        Process user message with LLM for flexible, context-aware responses.

        Args:
            state: Session state
            context_message: Optional context message to prepend

        Returns:
            LLM response string
        """
        if not self.client:
            # Fallback if no client available
            return "Lass uns über die Design-Details deines Anzugs sprechen!"

        # Get latest user message
        user_input = ""
        for msg in reversed(state.conversation_history):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_input = msg.get("content", "")
                break

        # Build conversation context
        messages = [
            {"role": "system", "content": self._get_system_prompt(state)},
        ]

        # Add context message if provided
        if context_message:
            messages.append({"role": "system", "content": f"CONTEXT: {context_message}"})

        # Add conversation history (last 10 messages)
        for msg in state.conversation_history[-10:]:
            if isinstance(msg, dict):
                role = "assistant" if msg.get("sender") in ["design_henk", "system"] else "user"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        # Add current user input if not already in history
        if user_input and not any(
            isinstance(m, dict) and m.get("role") == "user" and m.get("content") == user_input
            for m in messages
        ):
            messages.append({"role": "user", "content": user_input})

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
            )
            llm_response = response.choices[0].message.content

            logger.info(
                "[DesignHenk] ✅ LLM response generated (%d chars)",
                len(llm_response)
            )

            return llm_response

        except Exception as exc:
            logger.warning("[DesignHenk] LLM call failed: %s", exc)
            return "Lass uns über die Design-Details deines Anzugs sprechen!"

    def _load_style_catalog(self) -> dict:
        """
        Load style catalog from knowledge base.

        Returns:
            Style catalog dict or empty dict if failed
        """
        catalog_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "drive_mirror",
            "henk",
            "knowledge",
            "style_catalog.json"
        )

        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
                return catalog
        except FileNotFoundError:
            logger.warning("[DesignHenk] Style catalog not found at %s", catalog_path)
            return {}
        except Exception as exc:
            logger.warning("[DesignHenk] Failed to load style catalog: %s", exc)
            return {}

    def _get_style_knowledge(self, occasion: str = None) -> str:
        """
        Get relevant style knowledge based on occasion.

        Args:
            occasion: Optional occasion to filter (e.g., "Hochzeit", "Business", "Gala")

        Returns:
            Formatted style knowledge string
        """
        if not self.style_catalog:
            return ""

        dress_codes = self.style_catalog.get("dress_codes", {})

        # If specific occasion provided, try to match dress code
        if occasion:
            occasion_lower = occasion.lower()

            # Map occasions to dress codes
            occasion_mapping = {
                "hochzeit": "formal_evening",
                "gala": "formal_evening",
                "business": "business_formal",
                "vorstellungsgespräch": "business_formal",
                "arbeit": "business_casual",
                "meeting": "business_casual",
                "freizeit": "smart_casual",
                "restaurant": "smart_casual",
            }

            # Find matching dress code
            for key, dress_code_key in occasion_mapping.items():
                if key in occasion_lower:
                    if dress_code_key in dress_codes:
                        dc = dress_codes[dress_code_key]
                        return f"""
📋 EMPFEHLUNG FÜR {occasion.upper()}:
- Stil: {dc['name']}
- Erforderlich: {', '.join(dc.get('required_items', []))}
- Farben: {', '.join(dc.get('color_palette', []))}
- Stoffe: {', '.join(dc.get('fabric_recommendations', []))}
"""

        # Otherwise, return general overview
        knowledge = "\n📚 VERFÜGBARE DRESS CODES:\n"
        for code_key, code_data in dress_codes.items():
            occasions = code_data.get('occasions', [])
            colors = code_data.get('color_palette', [])
            knowledge += f"\n{code_data['name']}:\n"
            knowledge += f"  - Anlässe: {', '.join(occasions[:3])}\n"
            knowledge += f"  - Farben: {', '.join(colors[:3])}\n"

        return knowledge
