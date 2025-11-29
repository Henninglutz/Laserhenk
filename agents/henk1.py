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
        """
        print(f"=== HENK1 PROCESS: henk1_rag_queried = {state.henk1_rag_queried}")
        print(f"=== HENK1 PROCESS: customer_id = {state.customer.customer_id}")

        # If RAG has been queried (even if empty), needs assessment is complete
        if state.henk1_rag_queried:
            print("=== HENK1: RAG has been queried, marking complete")
            # Mark customer as identified (for Operator routing)
            if not state.customer.customer_id:
                state.customer.customer_id = f"TEMP_{state.session_id[:8]}"

            return AgentDecision(
                next_agent="operator",
                message="Needs assessment complete - customer informed about products",
                action=None,
                should_continue=True,
            )

        # First time in HENK1: Query RAG for product catalog
        print("=== HENK1: No RAG context, querying RAG")
        return AgentDecision(
            next_agent="operator",
            message="Starting needs assessment - querying product catalog",
            action="query_rag",
            action_params={
                "query": "Initial product catalog for new customer"
            },
            should_continue=True,
        )
