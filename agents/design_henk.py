"""Design HENK Agent - Design Präferenzen & Leadsicherung."""

import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState
from utils import load_prompt


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

    def __init__(self, prompt_name: str = "henk2_prompt_drive_style"):
        """
        Initialize Design HENK Agent.

        Args:
            prompt_name: Name of prompt file in Promt/ directory
        """
        super().__init__("design_henk")

        # Load system prompt
        try:
            self.system_prompt = load_prompt(prompt_name)
            print(f"✅ Design HENK: Loaded prompt '{prompt_name}'")
        except FileNotFoundError:
            print(f"⚠️  Design HENK: Prompt '{prompt_name}' not found, using fallback")
            self.system_prompt = self._get_fallback_prompt()

        # Initialize PydanticAI agent
        model = OpenAIModel(
            model_name=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        self.ai_agent = Agent(
            model=model,
            result_type=AgentDecision,
            system_prompt=self.system_prompt,
        )

    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if file not found."""
        return """Du bist Design HENK, der Design-Spezialist.

Deine Aufgabe:
1. Sammle Design-Präferenzen (Revers, Schulter, Bund, Futter)
2. Generiere Mood-Bild mit DALL-E
3. Sichere Lead im CRM (KRITISCH!)
4. Übergebe an LASERHENK für Maßerfassung

Antworte IMMER mit strukturiertem JSON gemäß AgentDecision Schema."""

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
