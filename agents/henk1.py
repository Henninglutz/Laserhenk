"""HENK1 Agent - Bedarfsermittlung (AIDA Prinzip)."""

from agents.base import AgentDecision, BaseAgent
from models.customer import CustomerType, SessionState


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

        Current implementation uses state-based decision logic.
        Phase 3 will add LLM integration for conversational needs assessment (AIDA).

        Returns:
            AgentDecision with next steps
        """

        # Check if customer type is determined
        if state.customer.customer_type == CustomerType.NEW:
            return AgentDecision(
                next_agent="operator",
                message="Needs assessment complete - new customer",
                action="query_rag",
                action_params={
                    "query": "Initial product catalog for new customer"
                },
                should_continue=True,
            )

        # Existing customer
        if state.customer.has_measurements:
            return AgentDecision(
                next_agent="operator",
                message="Existing customer with measurements",
                action="generate_initial_mood_image",
                action_params={"use_existing_data": True},
                should_continue=True,
            )

        # Default: continue conversation
        return AgentDecision(
            next_agent="operator",
            message="Continue needs assessment",
            action="continue_conversation",
            should_continue=True,
        )
