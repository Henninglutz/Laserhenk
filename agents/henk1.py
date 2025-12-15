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
- `state.henk1_mood_board_shown` - Flag ob Mood Board bereits gezeigt wurde
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
from typing import Optional

from openai import AsyncOpenAI

from agents.base import AgentDecision, BaseAgent
from agents.henk1_preferences import (
    IntentAnalysis,
    INTENT_EXTRACTION_PROMPT,
    fallback_intent_analysis,
)
from models.customer import SessionState

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

        # If RAG has been queried, show fabric images (if not shown yet)
        if state.henk1_rag_queried and not state.henk1_mood_board_shown:
            logger.info("[HENK1] RAG queried, now showing fabric images")

            # Check if we have fabric data in rag_context
            rag_context = getattr(state, "rag_context", None)
            if rag_context is None:
                rag_context = {}
            fabrics = rag_context.get("fabrics", [])

            if fabrics:
                # Extract occasion from conversation if available
                occasion = self._extract_style_info(state).get("occasion", "deinen Anlass")

                # Mark mood board as shown (we're showing fabric images instead)
                state.henk1_mood_board_shown = True

                return AgentDecision(
                    next_agent=None,
                    message=None,  # Tool will provide the message
                    action="show_fabric_images",
                    action_params={
                        "occasion": occasion,
                        "limit": 2,
                    },
                    should_continue=False,
                )
            else:
                logger.warning("[HENK1] No fabrics in rag_context, skipping image display")

        # If RAG has been queried and fabric images shown, mark complete and wait for user
        if state.henk1_rag_queried and state.henk1_mood_board_shown:
            logger.info("[HENK1] RAG queried and fabric images shown, HENK1 complete - waiting for user response")
            # Mark customer as identified (for Operator routing)
            if not state.customer.customer_id:
                state.customer.customer_id = f"TEMP_{state.session_id[:8]}"

            return AgentDecision(
                next_agent="operator",
                message=None,  # Fabric images already shown, no additional message needed
                action=None,
                should_continue=False,  # WAIT for user response to fabric images
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

        if intent.wants_fabrics:
            gaps = self._missing_core_needs(state)
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

            if state.henk1_rag_queried:
                return AgentDecision(
                    next_agent=None,
                    message=reply
                    + "\n\nIch habe dir gerade passende Stoffideen geschickt – sag kurz, was dir davon gefällt oder welche Farbe du lieber hättest.",
                    action=None,
                    should_continue=False,
                )

            print("=== HENK1: Customer ready for fabric recommendations, calling RAG")

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

    def _missing_core_needs(self, state: SessionState) -> list[str]:
        """Identify missing Bedarfsermittlung-Infos before Stoffe gezeigt werden."""

        text = " ".join(msg.get("content", "").lower() for msg in state.conversation_history if isinstance(msg, dict))
        style_info = self._extract_style_info(state)

        gaps: list[str] = []

        if not style_info.get("occasion"):
            gaps.append("für welchen Anlass der Anzug gedacht ist")
        if not style_info.get("colors"):
            gaps.append("welche Farbe(n) du willst")
        if "€" not in text and "euro" not in text and not any(char.isdigit() for char in text):
            gaps.append("dein Budget")
        timing_keywords = ["bis", "wann", "datum", "termin", "monat", "woche"]
        if not any(keyword in text for keyword in timing_keywords):
            gaps.append("wann du den Anzug brauchst")
        if not style_info.get("style_keywords"):
            gaps.append("ob du es klassisch oder modern magst")

        return gaps
    def _get_system_prompt(self) -> str:
        """Get HENK1 system prompt for needs assessment."""
        return """Du bist HENK1, der freundliche Maßanzug-Berater bei LASERHENK.

Deine Aufgabe - BEDARFSERMITTLUNG (alle Infos sammeln!):

✅ PFLICHT-INFOS (sammle ALLE bevor du fertig bist):
   1. ANLASS: Wofür braucht der Kunde den Anzug? (Hochzeit, Business, Gala, etc.)
   2. BUDGET: Wie viel möchte er ausgeben? (grobe Preisvorstellung)
   3. TIMING: Wann wird der Anzug benötigt? (Deadline)
   4. STIL: Welchen Stil bevorzugt er? (klassisch, modern, locker, etc.)
   5. FARBE: Welche Farben gefallen ihm? (blau, grau, schwarz, etc.)
   6. KONTAKT: Wenn klarer Kauf-/Terminwunsch → höflich nach Email und WhatsApp/Telefon fragen

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
        should_capture = intent.lead_ready or (state.henk1_rag_queried and state.henk1_mood_board_shown)

        if should_capture and not already_captured:
            state.customer.crm_lead_id = f"HENK1_LEAD_{state.session_id[:8]}"
            logger.info("[HENK1] Lead provisional secured during needs assessment")

    def _contact_request(self, state: SessionState, intent: IntentAnalysis) -> Optional[str]:
        """Frage nach Kontakt, wenn Lead klar ist und noch nichts vorliegt."""

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
            "grün": "green", "olive": "olive",
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
        }

        for keyword, style in style_keywords_map.items():
            if keyword in conversation_text and style not in style_info["style_keywords"]:
                style_info["style_keywords"].append(style)

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
