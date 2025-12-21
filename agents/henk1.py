"""HENK1 Agent - Bedarfsermittlung (AIDA Prinzip).

AGENT BESCHREIBUNG (für LLM als System Prompt):
------------------------------------------------
Du bist HENK1, der erste Kontaktpunkt und Bedarfsermittler bei LASERHENK.
Deine Aufgaben:

1. **AIDA Prinzip**:
   - **Attention**: Herzlicher Empfang, Eis brechen
   - **Interest**: Anlass verstehen, Farbpräferenzen erfragen
   - **Desire**: Stil-Inspiration wecken, Qualität vermitteln
   - **Action**: Zur Stoffauswahl überleiten

2. **Bedarfsermittlung**:
   - Anlass (Hochzeit, Business, Gala, etc.)
   - Budget-Rahmen (grob, nicht zu früh fragen)
   - Farbpräferenzen (Lieblingsfarben, Unternehmensfarben)
   - Stil-Richtung (klassisch, modern, sportlich)
   - Besondere Wünsche (Muster, Texturen, etc.)

3. **DALL-E Mood Board Generierung** (FRÜH im Prozess):
   - Nach 3-4 Konversationsrunden
   - Sobald Anlass + 1-2 Farben bekannt sind
   - Generiere visuelles Mood Board zur Inspiration
   - Zeige Stil-Richtungen und Farbkombinationen
   - Hilft dem Kunden sich zu orientieren

4. **Stoffempfehlung via RAG**:
   - Erst NACH Mood Board
   - Wenn Kunde sagt "zeig mir Stoffe" oder ähnliches
   - Extrahiere Suchkriterien aus Konversation
   - Trigger RAG Tool für konkrete Stoffempfehlungen

CONDITIONAL EDGES:
------------------
- Nach Begrüßung → Weiteres Gespräch
- Nach genug Kontext (3-4 Runden) → DALL-E Mood Board
- Nach Mood Board → Weiteres Gespräch, Feedback sammeln
- Wenn Kunde bereit → RAG Tool für Stoffe
- Nach RAG → Zu Design Henk übergeben

STATE ATTRIBUTES:
-----------------
- `state.conversation_history` - Vollständige Konversation
- `state.henk1_rag_queried` - Flag ob RAG bereits abgefragt wurde
- `state.henk1_fabrics_shown` - Flag ob Stoffliste (Top2+Alternativen) gezeigt wurde
- `state.henk1_to_design_payload` - Payload für Design Henk (Budget, Stil, Stoffe)

BEISPIEL-ABLAUF:
----------------
1. User: "Hallo"
   → HENK1: "Moin! 👋 Schön, dass du da bist! Planst du einen besonderen Anlass?"

2. User: "Ja, ich habe eine Hochzeit im Sommer"
   → HENK1: "Wunderbar! Welche Farben schweben dir vor?"

3. User: "Helles Blau und Beige wären schön"
   → HENK1: "Super Kombi! Eher klassisch-elegant oder modern-lässig?"
   → **TRIGGER: Mood Board Generierung** (Anlass + Farben bekannt)

4. [Mood Board wird generiert und angezeigt]
   → HENK1: "Hier ist ein Mood Board zur Inspiration! Was sagst du dazu?"

5. User: "Sehr schön! Zeig mir passende Stoffe"
   → HENK1: "Perfekt, ich stelle dir die besten Stoffe zusammen!"
   → **TRIGGER: RAG Tool**

6. [RAG Ergebnisse werden gezeigt]
   → Übergabe an Design Henk
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI

from agents.base import AgentDecision, BaseAgent
from agents.henk1_preferences import (
    IntentAnalysis,
    INTENT_EXTRACTION_PROMPT,
    fallback_intent_analysis,
)
from models.customer import SessionState
from models.fabric import FabricColor, FabricPattern
from models.handoff import Henk1ToDesignHenkPayload, OccasionType, StyleType
from tools.rag_tool import _find_local_image

logger = logging.getLogger(__name__)


class Henk1Agent(BaseAgent):
    """
    HENK1 - Bedarfsermittlung Agent.

    Aufgaben:
    - AIDA Prinzip (Attention, Interest, Desire, Action)
    - Smalltalk, Eisbrechen
    - Verstehen der Kundenbedürfnisse
    - Unterscheidung: Neukunde vs. Bestandskunde
    - Erste Bildgenerierung mit wenigen Kundeninfos
    """

    def __init__(self):
        """Initialize HENK1 Agent."""
        super().__init__("henk1")
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    async def process(self, state: SessionState) -> AgentDecision:
        """
        Process needs assessment phase.

        HENK1's job:
        - Welcome customer warmly (AIDA: Attention)
        - Ask about occasion, preferences, budget (Interest)
        - Build desire through conversation
        - Only query RAG when customer is ready to see fabrics
        """
        print(f"=== HENK1 PROCESS: henk1_rag_queried = {state.henk1_rag_queried}")
        print(f"=== HENK1 PROCESS: customer_id = {state.customer.customer_id}")
        print(f"=== HENK1 PROCESS: conversation_history length = {len(state.conversation_history)}")

        user_input = ""
        for msg in reversed(state.conversation_history):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_input = msg.get("content", "")
                break

        # SOFORT-FIX: Weste-Präferenz aus User-Input extrahieren
        user_lower = user_input.lower()

        # Check for NEGATIVE vest keywords first (ohne, keine, nicht)
        if "weste" in user_lower:
            negative_keywords = ["ohne weste", "keine weste", "nicht mit weste", "kein weste"]
            positive_keywords = ["mit weste", "haben weste", "möchte weste", "will weste", "weste ja"]

            if any(kw in user_lower for kw in negative_keywords):
                if state.wants_vest is None:
                    state.wants_vest = False
                    logger.info("[HENK1] ✅ FORCED: wants_vest = False from user input: '%s'", user_input[:60])
            elif any(kw in user_lower for kw in positive_keywords):
                if state.wants_vest is None:
                    state.wants_vest = True
                    logger.info("[HENK1] ✅ FORCED: wants_vest = True from user input: '%s'", user_input[:60])

        suit_choice = self._apply_suit_choice_from_input(state, user_input)

        if self._detect_contact_decline(user_input):
            state.henk1_contact_declined = True

        fabric_choice = self._detect_fabric_choice(user_input, state.shown_fabric_images)
        if fabric_choice is not None and state.shown_fabric_images:
            logger.info("[HENK1] Detected fabric choice: %s", fabric_choice)
            selected_index = min(
                max(fabric_choice, 0), len(state.shown_fabric_images) - 1
            )
            state.favorite_fabric = state.shown_fabric_images[selected_index]
            state.henk1_rag_queried = True
            state.henk1_fabrics_shown = True

            if state.henk1_cut_confirmed:
                follow_up = (
                    "Super, Stoff notiert. Lass uns direkt Passform & Revers klären – lieber"
                    " schlank oder klassisch geschnitten?"
                )
            else:
                follow_up = (
                    "Super, ich notiere den Stoff. Soll es ein 2- oder 3-Teiler werden?"
                    " Weste ja/nein?"
                )
                state.henk1_suit_choice_prompted = True
            return AgentDecision(
                next_agent="design_henk",
                message=follow_up,
                action=None,
                should_continue=True,  # FIXED: Must be True to continue to design_henk
            )

        if state.favorite_fabric:
            logger.info("[HENK1] Favorite fabric already set, skipping repeat")
            user_choice = suit_choice or self._extract_suit_choice(user_input)

            if state.henk1_cut_confirmed:
                variant_text = "2-Teiler" if state.suit_parts == "2" else "3-Teiler"
                vest_text = " ohne Weste" if state.wants_vest is False else " mit Weste"
                message = (
                    f"Perfekt, ich notiere: {variant_text}{vest_text}. "
                    "Lass uns noch Passform & Revers festlegen – eher schlank oder klassisch?"
                )
            elif user_choice:
                ack_parts = []
                if state.suit_parts:
                    ack_parts.append("2-Teiler" if state.suit_parts == "2" else "3-Teiler")
                if state.wants_vest is not None:
                    ack_parts.append("ohne Weste" if state.wants_vest is False else "mit Weste")

                missing = []
                if not state.suit_parts:
                    missing.append("2- oder 3-Teiler")
                if state.wants_vest is None:
                    missing.append("Weste ja/nein")

                message = "Notiert: " + ", ".join(ack_parts or ["Schnittdetails"])
                if missing:
                    message += ". Sag mir noch: " + " und ".join(missing) + "."
                else:
                    message += ". Lass uns Passform & Revers klären – schlank oder klassisch?"
            else:
                if state.henk1_suit_choice_prompted:
                    message = (
                        "Sag mir kurz, ob du einen 2- oder 3-Teiler willst und ob eine Weste dabei sein soll."
                    )
                else:
                    message = (
                        "Alles klar, lass uns jetzt den Schnitt klären. Lieber 2- oder 3-Teiler?"
                        " Brauchst du eine Weste?"
                    )
                    state.henk1_suit_choice_prompted = True
            return AgentDecision(
                next_agent="design_henk",
                message=message,
                action=None,
                should_continue=True,  # FIXED: Must be True to continue to design_henk
            )

        # If RAG has been queried, show curated fabric pair (mid + luxury)
        if state.henk1_rag_queried and not state.henk1_fabrics_shown:
            logger.info("[HENK1] RAG queried, now showing curated fabric pair")

            rag_context = getattr(state, "rag_context", None) or {}
            suggestions = (
                rag_context.get("fabrics")
                or rag_context.get("fabric_suggestions")
                or []
            )

            logger.info("[HENK1] Suggestions in rag_context: %d", len(suggestions))

            if suggestions:
                style_info = self._extract_style_info(state)
                prepared = self._prepare_fabric_presentations(
                    suggestions, style_info, state
                )

                state.henk1_fabrics_shown = True

                return AgentDecision(
                    next_agent=None,
                    message=prepared.get("message"),
                    action="show_fabric_pair",
                    action_params=prepared,
                    should_continue=False,
                )
            else:
                logger.warning("[HENK1] No fabrics in rag_context, asking for clarification")
                clarification_msg = (
                    "Ich habe gerade keine Stoffvorschläge aus der Datenbank. "
                    "Welche Farbe oder welches Muster soll ich für dich finden?"
                )
                return AgentDecision(
                    next_agent=None,
                    message=clarification_msg,
                    action=None,
                    should_continue=False,
                )

        # If RAG has been queried and fabric images shown, check if user responded
        if state.henk1_rag_queried and state.henk1_fabrics_shown:
            logger.info(
                "[HENK1] RAG queried and fabric images shown - checking for user response"
            )
            if not state.customer.customer_id:
                state.customer.customer_id = f"TEMP_{state.session_id[:8]}"

            # SOFORT-FIX: Check if user has responded after fabric images
            recent_user_messages = [
                msg for msg in state.conversation_history[-3:]
                if isinstance(msg, dict) and msg.get("role") == "user"
            ]

            if recent_user_messages and state.favorite_fabric:
                # User has responded and selected fabric → forward to Design HENK
                logger.info("[HENK1] ✅ User responded after fabrics, forwarding to Design HENK")
                return AgentDecision(
                    next_agent="design_henk",
                    message="Perfekt! Lass uns jetzt über Schnitt und Details sprechen...",
                    action=None,
                    should_continue=True,  # Continue to Design HENK
                )
            elif recent_user_messages and not state.favorite_fabric:
                # User responded but hasn't selected fabric yet
                # Check if user is requesting different fabrics (color change, more options, etc.)
                latest_message = recent_user_messages[-1].get("content", "").lower()

                # Keywords indicating user wants different/more fabrics
                change_keywords = [
                    "andere", "andere stoffe", "mehr stoffe", "weitere", "mehr",
                    "stoffe", "stoff",  # Fabric mentions
                    "blau", "grau", "schwarz", "braun", "beige", "rot", "gelb", "orange", "weiß", "dunkel", "hell",  # Colors
                    "nicht grün", "nicht diese", "andere farbe", "nicht",
                    "zeig mir", "hast du", "gibt es", "zeige",
                ]

                wants_different_fabrics = any(kw in latest_message for kw in change_keywords)

                if wants_different_fabrics:
                    logger.info("[HENK1] 🔄 User wants different fabrics, triggering new RAG search")
                    # Reset RAG state to allow new search
                    state.henk1_rag_queried = False
                    state.henk1_fabrics_shown = False  # Also reset this to force new images
                    # Don't return here - let the flow continue to LLM processing below
                else:
                    # User just commenting, no fabric change request → continue conversation
                    logger.info("[HENK1] User responded but no fabric selected yet, continuing conversation")
                    return AgentDecision(
                        next_agent=None,
                        message=None,
                        action=None,
                        should_continue=False,  # WAIT for fabric selection
                    )
            else:
                # No response yet → wait
                logger.info("[HENK1] No user response yet, waiting...")
                return AgentDecision(
                    next_agent=None,
                    message=None,
                    action=None,
                    should_continue=False,  # WAIT for user response
                )

        # NOTE: Old mood board generation (BEFORE RAG) has been removed
        # New flow: RAG first → then show real fabric images (not DALL-E mood board)

        # Always use LLM for conversation - no hardcoded welcome message
        print("=== HENK1: Processing customer message with LLM")

        # Get user's latest message from conversation history
        user_input = ""
        for msg in reversed(state.conversation_history):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_input = msg.get("content", "")
                break

        # Build conversation context
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
        ]

        # Add conversation history
        for msg in state.conversation_history[-10:]:  # Last 10 messages
            if isinstance(msg, dict):
                role = "assistant" if msg.get("sender") in ["henk1", "system"] else "user"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        # Add current user input if not already in history
        if user_input and not any(
            isinstance(m, dict) and m.get("role") == "user" and m.get("content") == user_input
            for m in messages
        ):
            messages.append({"role": "user", "content": user_input})

        if self.client:
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                temperature=0.7,
            )

            llm_response = response.choices[0].message.content
        else:
            llm_response = self._offline_reply(user_input, state)

        intent = await self._extract_intent(user_input, state)

        self._maybe_capture_lead(state, intent)

        contact_prompt = self._contact_request(state, intent)
        reply = (
            f"{llm_response}\n\n{contact_prompt}" if contact_prompt else llm_response
        )

        needs_snapshot = self._needs_snapshot(state)
        gaps = self._missing_core_needs(needs_snapshot)

        if (
            not intent.wants_fabrics
            and not gaps
            and not state.henk1_rag_queried
            and not state.henk1_fabrics_shown
        ):
            intent.wants_fabrics = True

        if intent.wants_fabrics:
            if gaps:
                questions = " ".join(gaps)
                return AgentDecision(
                    next_agent=None,
                    message=reply
                    + "\n\nBevor ich dir Stoffe zeige, sag mir bitte noch: "
                    + questions,
                    action=None,
                    should_continue=False,
                )

            self._persist_handoff_payload(state, needs_snapshot)

            is_new_search = self._is_new_fabric_search(user_input)

            if state.henk1_rag_queried and not is_new_search:
                return AgentDecision(
                    next_agent=None,
                    message=reply
                    + "\n\nIch habe dir gerade passende Stoffideen geschickt – sag kurz, was dir davon gefällt oder welche Farbe du lieber hättest.",
                    action=None,
                    should_continue=False,
                )

            print("=== HENK1: Customer ready for fabric recommendations, calling RAG")

            state.henk1_rag_queried = True

            return AgentDecision(
                next_agent="henk1",
                message=reply,  # Show LLM response before RAG results
                action="rag_tool",  # Trigger RAG tool
                action_params=intent.search_criteria,
                should_continue=True,
            )

        return AgentDecision(
            next_agent=None,
            message=reply,
            action=None,
            should_continue=False,
        )

    def _missing_core_needs(self, needs: dict) -> list[str]:
        """Identify missing Bedarfsermittlung-Infos before Stoffe gezeigt werden."""
        gaps: list[str] = []

        # CRITICAL: Only require colors - timing can be asked AFTER showing fabrics
        if not needs.get("colors"):
            gaps.append("welche Farbe(n) du willst")

        # Optional: Timing is nice-to-have but not blocking
        # Can be asked after fabrics are shown
        # if not needs.get("timing_hint"):
        #     gaps.append("wann du den Anzug brauchst (Termin oder Zeitraum)")

        return gaps

    def _needs_snapshot(self, state: SessionState) -> dict:
        """Collect normalized needs from the conversation to avoid double-asking."""

        conversation_text = " ".join(
            msg.get("content", "").lower()
            for msg in state.conversation_history
            if isinstance(msg, dict)
        )

        latest_user = next(
            (
                msg.get("content")
                for msg in reversed(state.conversation_history)
                if isinstance(msg, dict) and msg.get("role") == "user"
            ),
            None,
        )

        style_info = self._extract_style_info(state)

        budget_value, budget_status = self._extract_budget(conversation_text)
        timing_hint = self._extract_timing_hint(conversation_text, state)

        state.customer_budget_status = budget_status

        return {
            "occasion": style_info.get("occasion"),
            "colors": style_info.get("colors", []),
            "style_keywords": style_info.get("style_keywords", []),
            "patterns": style_info.get("patterns", []),
            "budget_eur": budget_value,
            "budget_status": budget_status,
            "timing_hint": timing_hint,
            "notes": latest_user,
        }

    def _extract_budget(self, conversation_text: str) -> tuple[Optional[float], str]:
        """Parse numeric budget and classify budget status."""

        import re

        lowered = conversation_text.lower()
        no_budget_keywords = [
            "kein budget",
            "keine preisvorstellung",
            "ohne budget",
            "egal",
        ]

        if any(keyword in lowered for keyword in no_budget_keywords):
            return None, "none"

        status = "unknown"
        match = re.search(r"(\d+[\.,]?\d*)", conversation_text)
        if not match:
            return None, status

        try:
            value = float(match.group(1).replace(",", "."))
            return value, "fixed"
        except ValueError:
            return None, status

    def _extract_timing_hint(
        self, conversation_text: str, state: SessionState
    ) -> Optional[str]:
        """Extract soft timing hints (e.g., seasons, quarters, relative weeks)."""

        import re

        soft_patterns = [
            r"in\s+\d+\s+(?:wochen|woche|monaten|monate|tagen|tage)",
            r"q[1-4]",
            r"sommer|winter|frühjahr|fruehjahr|fruhjahr|herbst|frühling|fruhling",
            r"januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember",
        ]

        for pattern in soft_patterns:
            match = re.search(pattern, conversation_text, re.IGNORECASE)
            if match:
                hint = match.group(0)
                if not state.customer.event_date:
                    state.customer.event_date = hint
                state.customer.event_date_hint = hint
                return hint

        return None

    def _persist_handoff_payload(self, state: SessionState, needs: dict) -> None:
        """Persist a validated handoff payload once Pflichtinfos liegen vor."""

        budget = needs.get("budget_eur")
        colors_raw: list[str] = needs.get("colors", []) or []
        patterns_raw: list[str] = needs.get("patterns", []) or []
        occasion_raw = needs.get("occasion")

        if not (budget and colors_raw and patterns_raw and occasion_raw):
            return

        color_mapping = {
            "navy": FabricColor.NAVY,
            "blue": FabricColor.NAVY,
            "dark grey": FabricColor.GRAU,
            "grey": FabricColor.GRAU,
            "light grey": FabricColor.HELLGRAU,
            "black": FabricColor.SCHWARZ,
            "brown": FabricColor.BRAUN,
            "beige": FabricColor.BEIGE,
            "camel": FabricColor.BEIGE,
            "olive": FabricColor.OLIV,
            "green": FabricColor.OLIV,
            "burgundy": FabricColor.BRAUN,
            "red": FabricColor.BRAUN,
        }

        pattern_mapping = {
            "fischgrat": FabricPattern.FISCHGRAT,
            "tweed": FabricPattern.STRUKTUR,
            "karo": FabricPattern.KARO,
            "nadelstreifen": FabricPattern.NADELSTREIFEN,
            "uni": FabricPattern.UNI,
        }

        colors = [color_mapping[c] for c in colors_raw if c in color_mapping]
        patterns = [pattern_mapping[p] for p in patterns_raw if p in pattern_mapping]

        if not colors or not patterns:
            return

        style = StyleType.BUSINESS
        if "casual" in (needs.get("style_keywords") or []):
            style = StyleType.SMART_CASUAL
        elif "modern" in (needs.get("style_keywords") or []):
            style = StyleType.BUSINESS
        elif "klassisch" in (needs.get("style_keywords") or []):
            style = StyleType.BUSINESS

        occasion_mapping = {
            "Business": OccasionType.BUSINESS_MEETING,
            "Everyday": OccasionType.EVERYDAY,
            "Hochzeit": OccasionType.WEDDING,
            "Gala": OccasionType.GALA,
            "Party": OccasionType.PARTY,
            "Feier": OccasionType.PARTY,
            "Formal": OccasionType.BUSINESS_MEETING,
            "Casual": OccasionType.EVERYDAY,
        }

        occasion = occasion_mapping.get(occasion_raw, OccasionType.OTHER)

        payload = {
            "budget_min": float(budget),
            "budget_max": float(budget),
            "style": style,
            "occasion": occasion,
            "patterns": patterns,
            "colors": colors,
            "customer_notes": needs.get("notes"),
        }

        try:
            validated = Henk1ToDesignHenkPayload(**payload).model_dump()
        except Exception:
            return

        state.henk1_to_design_payload = validated
        state.handoffs["design_henk"] = validated
    def _get_system_prompt(self) -> str:
        """Get HENK1 system prompt for needs assessment."""
        return """Du bist HENK1, der freundliche Maßanzug-Berater bei LASERHENK.

Deine Aufgabe - BEDARFSERMITTLUNG (alle Infos sammeln!):

✅ PFLICHT-INFOS (bevor du Stoffe zeigst):
   1. ANLASS: Wofür braucht der Kunde den Anzug? (Hochzeit, Business, Gala, etc.)
   2. TIMING: Wann wird der Anzug benötigt? Datum oder weiche Angabe (Sommer, in 6 Wochen)
   3. STIL: Welchen Stil bevorzugt er? (klassisch, modern, locker, etc.)
   4. FARBE: Welche Farben gefallen ihm? (blau, grau, schwarz, etc.)
   5. KONTAKT: Wenn klarer Kauf-/Terminwunsch → höflich nach Email und WhatsApp/Telefon fragen
   (Budget ist hilfreich, aber kein Pflichtfeld.)

💬 GESPRÄCHSFÜHRUNG:
- Sei herzlich, persönlich und kompetent
- Nutze lockere Sprache ("du", "Moin", emoji 🎩)
- Stelle 2-3 Fragen pro Nachricht, nicht zu viele auf einmal
- Gehe auf kurze Antworten ein und hake nach
- Beispiel: "eher locker" → "Cool! Und für welchen Anlass brauchst du ihn? Und hast du schon ein Budget im Kopf?"

🎯 STOLPERFALLEN:
- NICHT zu früh aufhören! Sammle ALLE Pflicht-Infos
- Bei kurzen Antworten → weitermachen, nicht abbrechen
- Erst wenn ALLE Infos da sind → Stoffe zeigen

📦 STOFFE ZEIGEN:
Wenn der Kunde bereit ist Stoffe zu sehen UND du alle Pflicht-Infos hast,
sage ihm dass du gleich passende Empfehlungen zusammenstellst.

Wichtig: Antworte IMMER auf Deutsch, kurz und freundlich."""

    def _offline_reply(self, user_input: str, state: SessionState) -> str:
        """Fallback-Antwort ohne LLM (z. B. in Tests)."""

        info = self._extract_style_info(state)
        questions = [
            "Alles klar, ich helfe dir gern!",
            "Wofür brauchst du den Anzug (z.B. Hochzeit, Business)?",
            "Welche Farben magst du?",
            "Bis wann soll er fertig sein?",
        ]

        if info.get("occasion"):
            questions = [
                "Top, das habe ich notiert!",
                "Welche Farbe(n) gefallen dir?",
                "Und bis wann brauchst du den Anzug?",
            ]

        return " ".join(questions)

    async def _extract_intent(self, user_input: str, state: SessionState) -> IntentAnalysis:
        """Delegate Intent- und Kriterien-Erkennung an das LLM (mit Fallback)."""
        has_api_key = bool(self.client)

        if not has_api_key:
            return fallback_intent_analysis(user_input, state.conversation_history)

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": INTENT_EXTRACTION_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "latest_user_message": user_input,
                                "conversation_snippet": state.conversation_history[-8:],
                            }
                        ),
                    },
                ],
            )

            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)

            return IntentAnalysis(
                wants_fabrics=bool(parsed.get("wants_fabrics")),
                search_criteria={
                    "query": user_input,
                    "colors": parsed.get("colors", []) or [],
                    "patterns": parsed.get("patterns", []) or [],
                },
                lead_ready=bool(parsed.get("lead_ready")),
            )
        except Exception as exc:  # pragma: no cover - robust fallback
            logger.warning("[HENK1] LLM intent extraction failed, using fallback", exc_info=exc)
            return fallback_intent_analysis(user_input, state.conversation_history)

    def _maybe_capture_lead(self, state: SessionState, intent: IntentAnalysis) -> None:
        """Setze ein CRM-Lead-Flag, sobald klarer Bedarf besteht."""
        already_captured = bool(state.customer.crm_lead_id)
        should_capture = intent.lead_ready or (
            state.henk1_rag_queried and state.henk1_fabrics_shown
        )

        if should_capture and not already_captured:
            state.customer.crm_lead_id = f"HENK1_LEAD_{state.session_id[:8]}"
            logger.info("[HENK1] Lead provisional secured during needs assessment")

    def _contact_request(self, state: SessionState, intent: IntentAnalysis) -> Optional[str]:
        """Frage nach Kontakt, wenn Lead klar ist und noch nichts vorliegt."""

        if state.henk1_contact_declined:
            return None

        if intent.wants_fabrics:
            return None

        if not intent.lead_ready:
            return None

        has_email_or_phone = bool(state.customer.email or state.customer.phone)
        already_asked = state.henk1_contact_requested

        if has_email_or_phone or already_asked:
            return None

        state.henk1_contact_requested = True
        return (
            "Damit ich dir direkt Stoffvorschläge schicken kann: "
            "Welche Email und ggf. WhatsApp-/Telefonnummer passt für dich?"
        )

    def _detect_contact_decline(self, user_input: str) -> bool:
        """Erkenne, wenn der Nutzer keine Kontaktdaten teilen will und bleibe im Chat."""

        text = (user_input or "").lower()
        if not text:
            return False

        decline_markers = [
            "kein e-mail", "keine e-mail", "keine email", "ohne email", "ohne mail",
            "keine nummer", "kein whatsapp", "kein telefon", "nur hier", "im chat",
            "nicht per mail", "zeige mir hier", "hier die stoffe", "nicht per email",
        ]

        return any(marker in text for marker in decline_markers)

    def _should_generate_mood_board(self, state: SessionState) -> bool:
        """
        Determine if we should generate a mood board.

        Criteria:
        - At least 3-4 conversation rounds
        - Mood board not shown yet
        - Some context gathered (occasion or colors mentioned)
        - RAG not queried yet (mood board comes BEFORE fabric selection)

        Args:
            state: Session State

        Returns:
            True if mood board should be generated
        """
        # Check if mood board already shown
        mood_board_shown = getattr(state, "henk1_mood_board_shown", False)
        if mood_board_shown:
            return False

        # Check if RAG already queried (mood board must come first)
        if state.henk1_rag_queried:
            return False

        # Need at least 3 conversation rounds (6 messages: 3 user, 3 assistant)
        if len(state.conversation_history) < 6:
            return False

        # Check if we have enough context
        context = self._extract_style_info(state)

        # Need at least occasion OR colors to generate meaningful mood board
        has_occasion = context.get("occasion") is not None
        has_colors = len(context.get("colors", [])) > 0

        return has_occasion or has_colors

    def _extract_style_info(self, state: SessionState) -> dict:
        """
        Extract style information from conversation for mood board generation.

        Args:
            state: Session State

        Returns:
            Dict with style_keywords, colors, occasion
        """
        style_info = {
            "style_keywords": [],
            "colors": [],
            "patterns": [],
            "occasion": None,
        }

        # Analyze conversation history
        conversation_text = " ".join(
            msg.get("content", "").lower()
            for msg in state.conversation_history
            if isinstance(msg, dict)
        )

        # Extract occasion
        occasion_keywords = {
            "hochzeit": "Hochzeit",
            "wedding": "Hochzeit",
            "business": "Business",
            "geschäft": "Business",
            "beruf": "Business",
            "arbeit": "Business",
            "job": "Business",
            "office": "Business",
            "alltag": "Everyday",
            "messe": "Business",
            "gala": "Gala",
            "empfang": "Gala",
            "party": "Party",
            "feier": "Feier",
            "formal": "Formal",
            "casual": "Casual",
            "lässig": "Casual",
        }

        for keyword, occasion in occasion_keywords.items():
            if keyword in conversation_text:
                style_info["occasion"] = occasion
                break

        # Extract colors
        color_keywords = {
            "blau": "blue", "navy": "navy", "dunkelblau": "navy",
            "grau": "grey", "dunkelgrau": "dark grey", "hellgrau": "light grey",
            "schwarz": "black",
            "braun": "brown", "beige": "beige", "camel": "camel",
            "grün": "green", "olive": "olive", "tannengrün": "green",
            "bordeaux": "burgundy", "rot": "red", "weinrot": "burgundy",
        }

        for keyword, color in color_keywords.items():
            if keyword in conversation_text and color not in style_info["colors"]:
                style_info["colors"].append(color)

        # Extract style keywords
        style_keywords_map = {
            "klassisch": "klassisch", "classic": "klassisch",
            "modern": "modern", "contemporary": "modern",
            "elegant": "elegant", "elegantly": "elegant",
            "sportlich": "sportlich", "casual": "casual",
            "formal": "formal", "formell": "formal",
            "schlicht": "minimalistisch", "minimalist": "minimalistisch",
            "tweed": "tweed",
        }

        pattern_keywords = {
            "fischgrat": "fischgrat",
            "tweed": "tweed",
            "karo": "karo",
            "kariert": "karo",
            "nadelstreifen": "nadelstreifen",
            "streifen": "nadelstreifen",
            "uni": "uni",
        }

        for keyword, style in style_keywords_map.items():
            if keyword in conversation_text and style not in style_info["style_keywords"]:
                style_info["style_keywords"].append(style)

        for keyword, pattern in pattern_keywords.items():
            if keyword in conversation_text and pattern not in style_info["patterns"]:
                style_info["patterns"].append(pattern)

        # Fallback style keywords if none found
        if not style_info["style_keywords"]:
            if style_info["occasion"] in ["Business", "Formal"]:
                style_info["style_keywords"] = ["elegant", "klassisch"]
            elif style_info["occasion"] in ["Hochzeit", "Gala"]:
                style_info["style_keywords"] = ["elegant", "festlich"]
            else:
                style_info["style_keywords"] = ["modern", "vielseitig"]

        logger.info(f"[HENK1] Extracted style info: {style_info}")
        return style_info

    def _build_fabric_title(self, tier: str, occasion: Optional[str], styles: list[str]) -> str:
        occasion_text = occasion or "deinen Anlass"
        style_hint = styles[0] if styles else "modern"
        if tier == "luxury":
            return f"Luxus-Statement für {occasion_text}"
        return f"Allrounder ({style_hint}) für {occasion_text}"

    def _prepare_fabric_presentations(
        self, suggestions: list[dict], style_info: dict, state: SessionState
    ) -> dict:
        """Normalize and persist fabric presentation details."""

        timestamp = datetime.now().isoformat()
        styles = style_info.get("style_keywords", []) or []
        occasion = style_info.get("occasion")

        preferred_colors = [c.lower() for c in style_info.get("colors", []) or []]

        normalized: list[dict] = []
        for suggestion in suggestions:
            fabric = suggestion.get("fabric", suggestion) or {}
            tier = suggestion.get("tier") or fabric.get("price_tier") or "mid"
            reference = (
                fabric.get("reference")
                or fabric.get("fabric_code")
                or fabric.get("code")
                or "unknown"
            )
            material = (
                fabric.get("material")
                or fabric.get("composition")
                or fabric.get("material_composition")
                or "Edle Wollmischung"
            )
            weight = fabric.get("weight_gsm") or fabric.get("weight")
            try:
                weight_int = int(weight) if weight is not None else None
            except (TypeError, ValueError):
                weight_int = None

            entry = {
                "price_tier": tier.lower() if isinstance(tier, str) else "mid",
                "reference": reference,
                "material": material,
                "weight_gsm": weight_int,
                "name": fabric.get("name") or fabric.get("color_name") or "Stoff",
                "color": fabric.get("color"),
                "pattern": fabric.get("pattern"),
                "image_url": fabric.get("image_url")
                or fabric.get("image_filename")
                or fabric.get("image"),
                "raw": fabric,
            }

            if not entry["image_url"] and reference:
                local_images = _find_local_image(reference)
                if local_images:
                    entry["image_url"] = local_images[0]
            normalized.append(entry)

        def _color_score(item: dict) -> float:
            if not preferred_colors:
                return 0.0

            haystack = " ".join(
                str(part).lower()
                for part in [item.get("color"), item.get("name"), item.get("reference")]
                if part
            )
            score = 0.0
            for pref in preferred_colors:
                if pref in haystack:
                    score += 1.5
            return score

        normalized = sorted(
            normalized,
            key=lambda item: (
                _color_score(item),
                1 if item.get("image_url") else 0,
                item.get("raw", {}).get("_similarity", 0),
            ),
            reverse=True,
        )

        def _pick_with_image(items: list[dict], tier: str) -> Optional[dict]:
            for item in items:
                if item.get("price_tier") == tier and item.get("image_url"):
                    return item
            for item in items:
                if item.get("image_url"):
                    return item
            return items[0] if items else None

        mid_choice = _pick_with_image(normalized, "mid")
        luxury_choice = _pick_with_image(
            [n for n in normalized if n is not mid_choice], "luxury"
        )

        top_fabrics = [f for f in [mid_choice, luxury_choice] if f]

        for fabric in top_fabrics:
            if not fabric.get("image_url") and fabric.get("reference"):
                local_images = _find_local_image(fabric.get("reference"))
                if local_images:
                    fabric["image_url"] = local_images[0]

        def _similarity_score(candidate: dict, anchor: dict) -> float:
            score = 0.0
            if anchor.get("color") and candidate.get("color") == anchor.get("color"):
                score += 1.5
            if anchor.get("pattern") and candidate.get("pattern") == anchor.get("pattern"):
                score += 1.2
            if anchor.get("weight_gsm") and candidate.get("weight_gsm"):
                diff = abs(anchor["weight_gsm"] - candidate["weight_gsm"])
                if diff <= 30:
                    score += 1.0
                elif diff <= 50:
                    score += 0.6
            if candidate.get("raw", {}).get("collection") and anchor.get("raw", {}).get(
                "collection"
            ):
                if (
                    candidate["raw"].get("collection")
                    == anchor["raw"].get("collection")
                ):
                    score += 1.0
            score += candidate.get("raw", {}).get("_similarity", 0) * 0.1
            return score

        remaining = [f for f in normalized if f not in top_fabrics]
        anchor = top_fabrics[0] if top_fabrics else None
        if anchor:
            remaining = sorted(
                remaining,
                key=lambda item: _similarity_score(item, anchor),
                reverse=True,
            )

        alternatives = remaining[:3]

        displayed_top: list[dict] = []
        for fabric in top_fabrics:
            tier = fabric.get("price_tier", "mid")
            title = self._build_fabric_title(tier, occasion, styles)
            entry = {
                "tier": tier,
                "title": title,
                "fabric": {
                    **fabric.get("raw", {}),
                    "reference": fabric.get("reference"),
                    "price_tier": tier,
                    "material": fabric.get("material"),
                    "weight_gsm": fabric.get("weight_gsm"),
                    "image_url": fabric.get("image_url"),
                },
                "description": [
                    fabric.get("material"),
                    f"Gewicht: {fabric.get('weight_gsm')} g/m²"
                    if fabric.get("weight_gsm")
                    else "Allround-Gewicht",
                    f"Ref: {fabric.get('reference')}",
                ],
            }
            displayed_top.append(entry)

        state.shown_fabric_images.extend(
            [
                {
                    "reference": fabric.get("reference"),
                    "tier": fabric.get("price_tier"),
                    "image_url": fabric.get("image_url"),
                    "title": self._build_fabric_title(
                        fabric.get("price_tier", "mid"), occasion, styles
                    ),
                    "material": fabric.get("material"),
                    "weight_gsm": fabric.get("weight_gsm"),
                    "timestamp": timestamp,
                }
                for fabric in top_fabrics
            ]
        )

        if displayed_top:
            state.fabric_presentation_history.append(
                {
                    "timestamp": timestamp,
                    "occasion": occasion,
                    "fabric_suggestions": displayed_top,
                }
            )

            references = [
                p["fabric"].get("reference") for p in displayed_top if p.get("fabric")
            ]
            existing_payload = state.henk1_to_design_payload or {}
            merged_payload = {**existing_payload, "fabric_references": references}
            state.henk1_to_design_payload = merged_payload
            state.handoffs["design_henk"] = merged_payload

        top_block_lines = ["2 Top-Stoffe – Mid & Luxury"]
        for fabric in displayed_top:
            fab = fabric.get("fabric", {})
            top_block_lines.append(
                f"- {fabric.get('title')}: Ref {fab.get('reference')} | "
                f"{fab.get('material')} | {fab.get('weight_gsm') or 'Allround'} g/m² | FOTO: {fab.get('image_url')}"
            )

        alt_block_lines = ["3 ähnliche Alternativen (ohne Foto)"]
        for alt in alternatives:
            alt_block_lines.append(
                f"- Ref {alt.get('reference')} | {alt.get('material')} | {alt.get('weight_gsm') or 'Allround'} g/m²"
            )

        message = "\n".join(top_block_lines + [""] + alt_block_lines)

        return {
            "fabric_suggestions": displayed_top,
            "alternatives": alternatives,
            "occasion": style_info.get("occasion", "deinen Anlass"),
            "message": message,
        }

    def _detect_fabric_choice(
        self, user_input: str, shown_fabric_images: Optional[list[dict]] = None
    ) -> Optional[int]:
        text = (user_input or "").lower()
        if not text:
            return None

        shown_fabric_images = shown_fabric_images or []

        code_match = next(
            (
                idx
                for idx, img in enumerate(shown_fabric_images)
                if img.get("fabric_code")
                and img.get("fabric_code", "").lower() in text
            ),
            None,
        )

        if code_match is not None:
            return code_match

        right_keywords = [
            "rechts",
            "rechte",
            "rechter",
            "zweite",
            "rechtsen",
            "rechtsen?",
            "2",
            "zweiter",
            "zweiten",
        ]
        left_keywords = ["links", "erste", "1", "ersten", "linke"]

        ordinal_map = {
            "erste": 0,
            "ersten": 0,
            "erster": 0,
            "zweite": 1,
            "zweiten": 1,
            "zweiter": 1,
            "dritte": 2,
            "dritten": 2,
            "dritter": 2,
            "vierte": 3,
            "vierten": 3,
            "vierter": 3,
            "fünfte": 4,
            "fünften": 4,
            "fünfter": 4,
        }

        match = re.search(r"(?:nummer|nr\.?|no\.?|#)\s*(\d+)", text)
        if match:
            return max(int(match.group(1)) - 1, 0)

        digit_match = re.search(r"\b([1-9])\b", text)
        if digit_match:
            return max(int(digit_match.group(1)) - 1, 0)

        for keyword, idx in ordinal_map.items():
            if keyword in text:
                return idx

        if any(key in text for key in right_keywords):
            return 1
        if any(key in text for key in left_keywords):
            return 0

        return None

    def _is_new_fabric_search(self, user_input: str) -> bool:
        text = (user_input or "").lower()
        triggers = [
            "andere stoffe",
            "mehr auswahl",
            "andere farbe",
            "zeig mehr",
            "nochmal",
            "andere muster",
        ]

        # Check for explicit triggers
        if any(trigger in text for trigger in triggers):
            return True

        # Check for REJECTION + COLOR (e.g., "ne, bitte grün")
        rejection_keywords = ["ne", "nein", "nicht", "lieber", "besser"]
        color_keywords = [
            "rot", "blau", "grün", "grau", "schwarz", "braun", "beige",
            "red", "blue", "green", "grey", "gray", "black", "brown",
            "dunkel", "hell", "marine", "navy", "olive"
        ]

        has_rejection = any(keyword in text for keyword in rejection_keywords)
        has_color = any(keyword in text for keyword in color_keywords)

        if has_rejection and has_color:
            logger.info(f"[HENK1] Rejection + color detected in '{text}', triggering new fabric search")
            return True

        return False

    def _extract_suit_choice(self, user_input: str) -> Optional[dict]:
        """Parse simple suit variant (2/3-teiler) and vest preference."""

        text = (user_input or "").lower()
        if not text:
            return None

        variant = None
        wants_vest = None

        if "zweiteiler" in text or "2-teiler" in text or "2 teiler" in text or text.strip() == "2":
            variant = "two_piece"
        elif "dreiteiler" in text or "3-teiler" in text or "3 teiler" in text or text.strip() == "3":
            variant = "three_piece"

        if "weste" in text:
            if any(kw in text for kw in ["kein", "nicht", "nein", "ohne"]):
                wants_vest = False
            elif any(kw in text for kw in ["ja", "mit", "gern", "bitte", "klar"]):
                wants_vest = True

        if variant or wants_vest is not None:
            return {"suit_variant": variant, "wants_vest": wants_vest}

        return None

    def _apply_suit_choice_from_input(
        self, state: SessionState, user_input: str
    ) -> Optional[dict]:
        """Persist parsed suit choices into session state and payload."""

        choice = self._extract_suit_choice(user_input)
        if not choice:
            return None

        updated = False
        variant = choice.get("suit_variant")
        if variant and not state.suit_parts:
            state.suit_parts = "2" if variant == "two_piece" else "3"
            updated = True

        wants_vest = choice.get("wants_vest")
        if wants_vest is not None and state.wants_vest is None:
            state.wants_vest = wants_vest
            updated = True

        if state.suit_parts and state.wants_vest is not None:
            state.henk1_cut_confirmed = True
            state.henk1_suit_choice_prompted = True

        if updated or state.henk1_cut_confirmed:
            payload = state.henk1_to_design_payload or {}
            if state.suit_parts:
                payload["suit_variant"] = (
                    "two_piece" if state.suit_parts == "2" else "three_piece"
                )
            if state.wants_vest is not None:
                payload["wants_vest"] = state.wants_vest

            state.henk1_to_design_payload = payload
            state.handoffs["design_henk"] = payload

        return choice
