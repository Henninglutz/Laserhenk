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

        # Check if this is first contact or ongoing conversation
        has_conversation = len(state.conversation_history) > 0

        if not has_conversation:
            # First contact with customer: Welcome and start needs assessment
            print("=== HENK1: First contact - starting needs assessment conversation")

            welcome_message = """
Lass uns kurz über dan Ablauf sprechen:

**Wir fertigen ausschließlich maßgeschneiderte Anzüge**
Der Weg dahin:
- Deine Wünsche
- Erste Ideen, Stile und Designs
- Maßnehmen mit Deinem Smartphone
- Fertigstellen vom Schnittbild, Kontrolle durch die Schneider und Rückmeldung an Dich VOR der Produktion

Und hast du schon eine Vorstellung vom Budget?

Je mehr ich über deine Vorstellungen weiß, desto besser kann ich dir passende Stoffe und Designs zeigen! 🎩"""

            return AgentDecision(
                next_agent="operator",
                message=welcome_message,
                action=None,
                should_continue=False,  # Wait for user response
            )

        else:
            # Ongoing conversation - acknowledge customer input and continue assessment
            print("=== HENK1: Ongoing conversation - processing customer response")

            # Simple acknowledgment message
            # In real implementation, this would use LLM to understand context
            response_message = """Perfekt! Eine Hochzeit im Sommer – da haben wir viele stilvolle Möglichkeiten! 🌞

Für Sommerhochzeiten empfehle ich leichtere Stoffe, die atmungsaktiv sind und trotzdem elegant aussehen.

**Noch ein paar Fragen:**
- Bist du Gast oder Bräutigam?
- Gibt es eine bestimmte Farbrichtung? (Navy, Grau, Beige, oder etwas Ausgefallenes?)
- Budget-Rahmen ungefähr?

Dann kann ich dir gleich passende Stoffe zeigen! 🎩"""

            return AgentDecision(
                next_agent="operator",
                message=response_message,
                action=None,
                should_continue=False,  # Wait for next user response
            )
