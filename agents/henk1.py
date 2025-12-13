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

import logging
import os
from openai import AsyncOpenAI
from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState
from typing import Optional

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
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
            rag_context = getattr(state, "rag_context", {})
            fabrics = rag_context.get("fabrics", [])

            if fabrics:
                # Extract occasion from conversation if available
                style_info = self._extract_style_info(state)
                occasion = style_info.get("occasion", "deinen Anlass")

                # Store customer preferences for CRM and DALL-E
                state.customer_preferences = {
                    "occasion": style_info.get("occasion"),
                    "colors": style_info.get("colors", []),
                    "style_keywords": style_info.get("style_keywords", []),
                    "budget": style_info.get("budget"),
                    "extracted_at": "henk1_fabric_display",
                }

                # Mark mood board as shown (we're showing fabric images)
                state.henk1_mood_board_shown = True

                return AgentDecision(
                    next_agent="operator",
                    message=None,  # Tool will provide the message
                    action="show_fabric_images",
                    action_params={
                        "occasion": occasion,
                        "limit": 3,  # Show 2-3 fabric images for initial selection
                    },
                    should_continue=False,  # Wait for user to select fabric
                )
            else:
                logger.warning("[HENK1] No fabrics in rag_context, skipping image display")

        # If RAG queried and fabric images shown, wait for user to select fabric
        if state.henk1_rag_queried and state.henk1_mood_board_shown:
            logger.info("[HENK1] Fabric images shown, waiting for user fabric selection")

            # Check if user selected a fabric
            user_input = ""
            for msg in reversed(state.conversation_history):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_input = msg.get("content", "")
                    break

            # Check for fabric selection (e.g., "Nummer 1", "der erste", "Stoff 2")
            fabric_selected, fabric_index = self._detect_fabric_selection(user_input)

            if fabric_selected:
                logger.info(f"[HENK1] User selected fabric {fabric_index}")

                # Get selected fabric from rag_context
                rag_context = getattr(state, "rag_context", {})
                fabrics = rag_context.get("fabrics", [])

                if fabric_index < len(fabrics):
                    selected_fabric = fabrics[fabric_index]

                    # Extract style info for outfit generation
                    style_info = self._extract_style_info(state)

                    # Update customer preferences with selected fabric
                    if not state.customer_preferences:
                        state.customer_preferences = {}
                    state.customer_preferences.update({
                        "selected_fabric_code": selected_fabric.get("fabric_code"),
                        "selected_fabric_name": selected_fabric.get("name"),
                        "selected_fabric_color": selected_fabric.get("color"),
                        "fabric_selected_at": "henk1_user_selection",
                    })

                    # Trigger outfit visualization with selected fabric
                    return AgentDecision(
                        next_agent="operator",
                        message="Perfekt! Lass mich dir zeigen, wie dein Anzug damit aussehen würde...",
                        action="generate_outfit",
                        action_params={
                            "fabric_data": selected_fabric,
                            "occasion": style_info.get("occasion", "elegant occasion"),
                            "style_keywords": style_info.get("style_keywords", []),
                            "session_id": state.session_id,
                        },
                        should_continue=True,
                    )

            # Mark customer as identified (for Operator routing)
            if not state.customer.customer_id:
                state.customer.customer_id = f"TEMP_{state.session_id[:8]}"

            # Wait for user to select fabric or ask another question
            return AgentDecision(
                next_agent="operator",
                message=None,  # No automatic message, wait for user
                action=None,
                should_continue=False,  # Wait for user input
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

        # Call LLM
        response = await self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            temperature=0.7,
        )

        llm_response = response.choices[0].message.content

        # Check if we should query RAG (simple keyword detection for now)
        should_query_rag = self._should_query_rag(user_input, state)

        if should_query_rag:
            print("=== HENK1: Customer ready for fabric recommendations, calling RAG")

            # Extract search criteria from conversation
            criteria = self._extract_search_criteria(user_input, state)

            return AgentDecision(
                next_agent="operator",
                message=llm_response,  # Show LLM response before RAG results
                action="query_rag",  # Trigger RAG tool
                action_params=criteria,  # Pass extracted criteria
                should_continue=True,
            )
        else:
            # Continue conversation
            return AgentDecision(
                next_agent="operator",
                message=llm_response,
                action=None,
                should_continue=False,  # Wait for user response
            )
    def _get_system_prompt(self) -> str:
        """Get HENK1 system prompt for needs assessment."""
        return """Du bist HENK1, der freundliche Maßanzug-Berater bei LASERHENK.

Deine Aufgabe:
- Führe eine natürliche Bedarfsermittlung durch (AIDA-Prinzip)
- Finde heraus: Anlass, Farbwünsche, Stoffpräferenzen, Budget
- Sei herzlich, persönlich und kompetent
- Nutze lockere Sprache ("du", "Moin", emoji 🎩)
- Stelle 2-3 Fragen pro Nachricht, nicht zu viele auf einmal

Wenn der Kunde bereit ist Stoffe zu sehen (z.B. "zeig mir Stoffe", "welche Optionen gibt es", "lass mal sehen"),
sage ihm dass du gleich passende Empfehlungen zusammenstellst.

Wichtig: Antworte IMMER auf Deutsch, kurz und freundlich."""

    def _should_query_rag(self, user_input: str, state: SessionState) -> bool:
        """Determine if we should query RAG based on user input."""
        user_input_lower = user_input.lower()

        # Keywords that indicate customer wants to see fabrics or images
        fabric_keywords = [
            # Direct fabric requests
            "stoff", "stoffe", "zeig", "zeigen", "empfehlung", "empfehlungen",
            "option", "optionen", "auswahl", "angebot", "material", "materialien",
            "vorschlag", "vorschläge", "lass", "sehen", "haben",
            # Image/visual requests
            "bild", "bilder", "foto", "fotos", "visuell", "ansehen",
            # Color mentions with action verbs
            "blau", "navy", "grau", "schwarz", "braun", "beige", "grün",
            # Quality/fabric-related terms
            "qualität", "wolle", "leinen", "baumwolle", "seide", "kaschmir",
            "muster", "farbe", "farben", "farbrichtung",
        ]

        # Check if any keyword is in user input
        has_fabric_request = any(keyword in user_input_lower for keyword in fabric_keywords)

        # Check if we have enough context (at least 2 messages in conversation)
        has_context = len(state.conversation_history) >= 2

        return has_fabric_request and has_context

    def _extract_search_criteria(self, user_input: str, state: SessionState) -> dict:
        """Extract search criteria from conversation context."""
        user_input_lower = user_input.lower()

        # Extract colors (simple keyword matching)
        colors = []
        color_keywords = {
            "mittelblau": "Blue", "blau": "Blue", "navy": "Navy", "dunkelblau": "Navy",
            "hellblau": "Light Blue", "königsblau": "Royal Blue",
            "grau": "Grey", "dunkelgrau": "Dark Grey", "hellgrau": "Light Grey",
            "schwarz": "Black",
            "braun": "Brown", "beige": "Beige", "camel": "Camel",
            "grün": "Green", "olive": "Olive",
            "bordeaux": "Burgundy", "rot": "Red", "weinrot": "Burgundy",
        }

        for keyword, color in color_keywords.items():
            if keyword in user_input_lower:
                colors.append(color)

        # Extract patterns
        patterns = []
        pattern_keywords = {
            "uni": "Solid", "einfarbig": "Solid",
            "streifen": "Stripes", "gestreift": "Stripes",
            "karo": "Check", "kariert": "Check",
            "fischgrat": "Herringbone",
        }

        for keyword, pattern in pattern_keywords.items():
            if keyword in user_input_lower:
                patterns.append(pattern)

        # If no specific criteria found, use conversation history
        if not colors and not patterns:
            # Check full conversation for context
            for msg in state.conversation_history[-5:]:
                content = msg.get("content", "").lower()
                for keyword, color in color_keywords.items():
                    if keyword in content and color not in colors:
                        colors.append(color)
                for keyword, pattern in pattern_keywords.items():
                    if keyword in content and pattern not in patterns:
                        patterns.append(pattern)

        return {
            "query": user_input,
            "colors": colors,
            "patterns": patterns,
        }

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
            Dict with style_keywords, colors, occasion, budget
        """
        style_info = {
            "style_keywords": [],
            "colors": [],
            "occasion": None,
            "budget": None,
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

        # Extract budget hints
        budget_keywords = {
            "kein budget": "unlimited",
            "keine grenze": "unlimited",
            "unbegrenzt": "unlimited",
            "unter 1000": "under_1000",
            "unter 1500": "under_1500",
            "unter 2000": "under_2000",
            "bis 1000": "under_1000",
            "bis 1500": "under_1500",
            "bis 2000": "under_2000",
            "günstig": "budget_conscious",
            "erschwinglich": "budget_conscious",
            "premium": "premium",
            "luxus": "luxury",
            "hochwertig": "premium",
        }

        for keyword, budget in budget_keywords.items():
            if keyword in conversation_text:
                style_info["budget"] = budget
                break

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

    def _detect_fabric_selection(self, user_input: str) -> tuple[bool, int]:
        """
        Detect if user selected a fabric and return (selected, fabric_index).

        Args:
            user_input: User's message

        Returns:
            Tuple of (fabric_selected: bool, fabric_index: int)
            fabric_index is 0-based

        Examples:
            "Nummer 1" → (True, 0)
            "der erste Stoff" → (True, 0)
            "Stoff 2" → (True, 1)
            "den zweiten bitte" → (True, 1)
            "noch mehr Optionen" → (False, -1)
        """
        user_input_lower = user_input.lower()

        # Direct number detection
        number_keywords = {
            "1": 0,
            "2": 1,
            "3": 2,
            "erste": 0,
            "erster": 0,
            "ersten": 0,
            "zweite": 1,
            "zweiter": 1,
            "zweiten": 1,
            "dritte": 2,
            "dritter": 2,
            "dritten": 2,
        }

        for keyword, index in number_keywords.items():
            if keyword in user_input_lower:
                return True, index

        # Check for "nummer X" pattern
        import re
        number_match = re.search(r'nummer\s*(\d+)', user_input_lower)
        if number_match:
            fabric_num = int(number_match.group(1))
            if 1 <= fabric_num <= 3:
                return True, fabric_num - 1

        # Check for "stoff X" pattern
        stoff_match = re.search(r'stoff\s*(\d+)', user_input_lower)
        if stoff_match:
            fabric_num = int(stoff_match.group(1))
            if 1 <= fabric_num <= 3:
                return True, fabric_num - 1

        return False, -1
