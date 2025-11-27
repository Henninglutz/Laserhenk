"""LLM Mixin for Agents - Optional GPT-4 Integration."""

from typing import Any, Optional


class LLMMixin:
    """
    Mixin class to add LLM capabilities to agents.

    Agents can optionally inherit from this to get GPT-4 enhanced decision-making.
    Falls back gracefully to state-based logic if LLM is not available.
    """

    def __init__(self, *args, enable_llm: bool = False, **kwargs):
        """
        Initialize LLM capabilities.

        Args:
            enable_llm: Enable LLM-enhanced decision making
        """
        super().__init__(*args, **kwargs)
        self.enable_llm = enable_llm
        self._llm_service = None

    @property
    def llm_service(self):
        """Lazy-load LLM service."""
        if self.enable_llm and self._llm_service is None:
            try:
                from services.llm_service import LLMService
                self._llm_service = LLMService()
            except Exception as e:
                print(f"Warning: Could not initialize LLM service for {getattr(self, 'agent_name', 'agent')}: {e}")
                print("Falling back to state-based decision logic")
                self.enable_llm = False
        return self._llm_service

    async def generate_conversational_response(
        self,
        system_prompt: str,
        user_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Generate conversational response using LLM.

        Args:
            system_prompt: System instructions
            user_message: User input
            context: Additional context

        Returns:
            Generated response or fallback message
        """
        if not self.enable_llm or not self.llm_service:
            agent_name = getattr(self, 'agent_name', 'Agent')
            return f"[{agent_name}] Processing request (LLM mode disabled)"

        return await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_message=user_message,
            context=context,
        )

    async def make_llm_decision(
        self,
        system_prompt: str,
        state_description: str,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Use LLM to make intelligent routing/action decisions.

        Args:
            system_prompt: Agent-specific system prompt
            state_description: Current state formatted for LLM
            context: Additional context

        Returns:
            LLM decision text
        """
        if not self.enable_llm or not self.llm_service:
            return None

        return await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_message=state_description,
            context=context,
            temperature=0.3,  # Lower temperature for decision-making
        )
