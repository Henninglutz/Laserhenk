"""LLM Service for GPT-4 Integration."""

from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel

from config.settings import get_settings


class LLMService:
    """
    LLM Service for intelligent agent decision-making.

    Integrates OpenAI GPT-4 for conversational AI and decision logic.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM Service.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model name (defaults to settings)
        """
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        context: Optional[dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Generate LLM response.

        Args:
            system_prompt: System instructions for the agent
            user_message: User input or current state description
            context: Additional context (customer data, preferences, etc.)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum response length

        Returns:
            Generated response text
        """
        messages = [{"role": "system", "content": system_prompt}]

        # Add context if provided
        if context:
            context_str = self._format_context(context)
            messages.append({
                "role": "system",
                "content": f"Current Context:\n{context_str}"
            })

        # Add user message
        messages.append({"role": "user", "content": user_message})

        # Generate response
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    async def generate_structured_response(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[BaseModel],
        context: Optional[dict[str, Any]] = None,
        temperature: float = 0.7,
    ) -> BaseModel:
        """
        Generate structured response using Pydantic model.

        Args:
            system_prompt: System instructions
            user_message: User input
            response_model: Pydantic model for structured output
            context: Additional context
            temperature: Sampling temperature

        Returns:
            Pydantic model instance
        """
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            context_str = self._format_context(context)
            messages.append({
                "role": "system",
                "content": f"Current Context:\n{context_str}"
            })

        # Add format instructions
        schema_str = response_model.model_json_schema()
        messages.append({
            "role": "system",
            "content": f"Respond with JSON matching this schema:\n{schema_str}"
        })

        messages.append({"role": "user", "content": user_message})

        # Generate response with JSON mode
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        # Parse to Pydantic model
        response_json = response.choices[0].message.content
        return response_model.model_validate_json(response_json)

    def _format_context(self, context: dict[str, Any]) -> str:
        """
        Format context dictionary for LLM consumption.

        Args:
            context: Context dictionary

        Returns:
            Formatted context string
        """
        lines = []
        for key, value in context.items():
            if isinstance(value, BaseModel):
                lines.append(f"{key}: {value.model_dump_json()}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)


# ============================================================================
# PROMPT LOADING (from Google Drive)
# ============================================================================


class PromptLoader:
    """
    Load system prompts from Google Drive.

    Prompts are stored externally in Google Drive for easy editing
    without code changes.
    """

    def __init__(self, drive_folder_id: Optional[str] = None):
        """
        Initialize prompt loader.

        Args:
            drive_folder_id: Google Drive folder ID for prompts
        """
        settings = get_settings()
        self.drive_folder_id = drive_folder_id or settings.google_drive_folder_id

    async def load_prompt(self, agent_name: str) -> str:
        """
        Load system prompt for specific agent from Google Drive.

        Args:
            agent_name: Agent name (operator, henk1, design_henk, laserhenk)

        Returns:
            System prompt text
        """
        # TODO: Implement Google Drive API integration
        # This would:
        # 1. Authenticate with Google Service Account
        # 2. Find prompt file: f"{agent_name}_prompt.txt"
        # 3. Download and return content

        # Placeholder for now
        return f"System prompt for {agent_name} (loaded from Google Drive)"

    async def load_all_prompts(self) -> dict[str, str]:
        """
        Load all agent prompts from Google Drive.

        Returns:
            Dictionary mapping agent_name → prompt
        """
        agents = ["operator", "henk1", "design_henk", "laserhenk"]
        prompts = {}

        for agent_name in agents:
            prompts[agent_name] = await self.load_prompt(agent_name)

        return prompts
