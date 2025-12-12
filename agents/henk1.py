"""HENK1 Agent - Bedarfsermittlung (AIDA Prinzip)."""

import os
from openai import AsyncOpenAI
from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState
from typing import Optional


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

        # If RAG has been queried and customer saw fabrics, mark complete
        if state.henk1_rag_queried:
            print("=== HENK1: RAG has been queried, marking complete")
            # Mark customer as identified (for Operator routing)
            if not state.customer.customer_id:
                state.customer.customer_id = f"TEMP_{state.session_id[:8]}"

            return AgentDecision(
                next_agent="operator",
                message=None,  # No message - RAG tool already provided results to user
                action=None,
                should_continue=True,
            )

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

        # Keywords that indicate customer wants to see fabrics
        fabric_keywords = [
            "stoff", "stoffe", "zeig", "zeigen", "empfehlung", "empfehlungen",
            "option", "optionen", "auswahl", "angebot", "material", "materialien",
            "vorschlag", "vorschläge", "lass", "sehen", "haben",
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
            "blau": "Blue", "navy": "Navy", "dunkelblau": "Navy",
            "grau": "Grey", "dunkelgrau": "Dark Grey", "hellgrau": "Light Grey",
            "schwarz": "Black",
            "braun": "Brown", "beige": "Beige", "camel": "Camel",
            "grün": "Green", "olive": "Olive",
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
