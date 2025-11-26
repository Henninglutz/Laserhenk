"""Design HENK Agent - Design Präferenzen & Leadsicherung."""

from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState


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
        Process design preferences and lead securing.

        Returns:
            AgentDecision with next steps
        """
        # Hier würde die LLM-Logik für Design-Abfrage stehen
        # Für jetzt: Struktur-Placeholder

        # Check if we need to query RAG for design options
        if not state.rag_context:
            return AgentDecision(
                next_agent="design_henk",
                message="Querying RAG for design options",
                action="query_rag",
                action_params={
                    "query": "Design options: Revers, Futter, Schulter, Bund"
                },
                should_continue=True,
            )

        # Check if design preferences are collected
        preferences_complete = (
            state.design_preferences.revers_type is not None
            and state.design_preferences.shoulder_padding is not None
        )

        if not preferences_complete:
            return AgentDecision(
                next_agent="design_henk",
                message="Collecting design preferences",
                action="collect_preferences",
                should_continue=True,
            )

        # Generate mood image with DALLE
        if not state.mood_image_url:
            return AgentDecision(
                next_agent="design_henk",
                message="Generating mood image",
                action="generate_dalle_image",
                action_params={
                    "design_preferences": state.design_preferences.model_dump(),
                    "customer_context": state.rag_context,
                },
                should_continue=True,
            )

        # Mandatory: Leadsicherung mit CRM**
        if not state.customer.crm_lead_id:
            return AgentDecision(
                next_agent="design_henk",
                message="Securing lead in CRM",
                action="create_crm_lead",
                action_params={
                    "customer": state.customer.model_dump(),
                    "design_preferences": state.design_preferences.model_dump(),
                    "mood_image": state.mood_image_url,
                },
                should_continue=True,
            )

        # Design phase complete → route to operator
        return AgentDecision(
            next_agent="operator",
            message="Design phase complete, lead secured",
            action="complete_design_phase",
            should_continue=True,
        )
