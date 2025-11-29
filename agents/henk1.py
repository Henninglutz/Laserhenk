"""HENK1 Agent - Bedarfsermittlung (AIDA Prinzip)."""

import os
from typing import Optional

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState
from utils import load_prompt


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

    def __init__(self, prompt_name: str = "henk1_prompt"):
        """
        Initialize HENK1 Agent.

        Args:
            prompt_name: Name of prompt file in Promt/ directory
        """
        super().__init__("henk1")

        # Load system prompt
        try:
            self.system_prompt = load_prompt(prompt_name)
            print(f"✅ HENK1: Loaded prompt '{prompt_name}'")
        except FileNotFoundError:
            print(f"⚠️  HENK1: Prompt '{prompt_name}' not found, using fallback")
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
        return """Du bist HENK1, der Bedarfsermittlungs-Agent.

Deine Aufgabe:
1. Begrüße den Kunden freundlich
2. Finde heraus: Anlass, Zeitrahmen, Budget, Stilvorlieben
3. Nutze das AIDA-Prinzip (Attention, Interest, Desire, Action)
4. Wenn genug Info gesammelt: Übergebe an Design HENK

Antworte IMMER mit strukturiertem JSON gemäß AgentDecision Schema."""

    async def process(self, state: SessionState) -> AgentDecision:
        """
        Process needs assessment phase.
        """
        print(f"=== HENK1 PROCESS: henk1_rag_queried = {state.henk1_rag_queried}")
        print(f"=== HENK1 PROCESS: customer_id = {state.customer.customer_id}")

        # MVP: Simple rule-based logic (LLM integration later)
        # For now: Same logic as before but with loaded prompts ready

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

    async def process_with_llm(self, state: SessionState, user_message: str) -> AgentDecision:
        """
        Process with LLM (for future use when we have actual conversations).

        Args:
            state: Current session state
            user_message: User's message

        Returns:
            Agent decision from LLM
        """
        # Build context from state
        context = self._build_context(state)

        # Run LLM
        result = await self.ai_agent.run(
            f"""
Context: {context}

User message: {user_message}

Based on the context and user message, decide the next action.
Return a structured AgentDecision.
"""
        )

        return result.data

    def _build_context(self, state: SessionState) -> str:
        """Build context string from session state."""
        return f"""
Session ID: {state.session_id}
Customer ID: {state.customer.customer_id or 'Unknown'}
RAG Queried: {state.henk1_rag_queried}
Conversation History: {len(state.conversation_history)} messages
"""
