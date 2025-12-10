"""HENK1 Agent - Bedarfsermittlung (AIDA Prinzip)."""

from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState


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

        # First contact with customer: Welcome and start needs assessment
        print("=== HENK1: First contact - starting needs assessment conversation")

        # Create a warm, personal welcome message following AIDA principle
        welcome_message = """Moin! Schön, dass du hier bist! 👋

Ein maßgeschneiderter Anzug – da bist du bei mir genau richtig. Ich bin HENK und helfe dir, den perfekten Anzug für dich zu finden.

Lass uns kurz über deine Wünsche sprechen:

**Für welchen Anlass brauchst du den Anzug?**
- Hochzeit (als Gast oder Bräutigam?)
- Business/Büro
- Besonderes Event
- Oder einfach für den Alltag?

**Und hast du schon eine Vorstellung vom Budget?**

Je mehr ich über deine Vorstellungen weiß, desto besser kann ich dir passende Stoffe und Designs zeigen! 🎩"""

        return AgentDecision(
            next_agent="operator",
            message=welcome_message,
            action=None,
            should_continue=False,  # Wait for user response
        )
