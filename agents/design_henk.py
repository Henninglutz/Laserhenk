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
        if not state.design_rag_queried:
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
            # TODO: Replace with actual LLM conversation to collect preferences
            # For now: Mock data to prevent infinite loop
            state.design_preferences.revers_type = "Spitzrevers"
            state.design_preferences.shoulder_padding = "mittel"
            state.design_preferences.waistband_type = "bundfalte"

            return AgentDecision(
                next_agent="operator",
                message="Design preferences collected (mock data)",
                action=None,
                should_continue=True,
            )

        # Generate mood image with DALLE
        if not state.mood_image_url:
            # TODO: Replace with actual DALL-E API call
            # For now: Mock URL to prevent infinite loop
            state.mood_image_url = "https://mock-dalle-image.jpg"

            return AgentDecision(
                next_agent="operator",
                message="Mood image generated (mock)",
                action=None,
                should_continue=True,
            )

        # Mandatory: Leadsicherung mit CRM**
        if not state.customer.crm_lead_id:
            # TODO: Replace with actual CRM API call
            # For now: Mock CRM ID to prevent infinite loop
            state.customer.crm_lead_id = f"MOCK_CRM_{state.session_id[:8]}"

            return AgentDecision(
                next_agent="operator",
                message="Lead secured in CRM (mock)",
                action=None,
                should_continue=True,
            )

        # Design phase complete → route to operator
        return AgentDecision(
            next_agent="operator",
            message="Design phase complete, lead secured",
            action="complete_design_phase",
            should_continue=True,
        )
