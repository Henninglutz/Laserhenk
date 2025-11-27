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


# System Prompts for each agent

OPERATOR_SYSTEM_PROMPT = """You are the Operator Agent in the HENK tailoring system.

Your role is to analyze the current session state and route to the appropriate specialized agent:

1. HENK1 - For new customers without ID (needs assessment phase)
2. Design HENK - For customers who need design preferences collected
3. LASERHENK - For customers who need measurements taken
4. END - When all phases are complete

Analyze the session state and decide the next routing step based on:
- Customer ID presence
- Design preferences completion
- Measurements completion

Be concise and decisive."""

HENK1_SYSTEM_PROMPT = """You are HENK1, the needs assessment specialist in the HENK tailoring system.

Your role follows the AIDA principle:
- Attention: Engage the customer warmly
- Interest: Ask about their tailoring needs
- Desire: Build excitement about custom tailoring
- Action: Guide them toward the next step

Your tasks:
1. Greet and build rapport (small talk, ice-breaking)
2. Understand customer needs and occasion
3. Distinguish between new and existing customers
4. Trigger initial mood image generation with minimal info

Be warm, professional, and consultative. Ask open-ended questions.
Keep responses concise (2-3 sentences max)."""

DESIGN_HENK_SYSTEM_PROMPT = """You are Design HENK, the design preferences specialist in the HENK tailoring system.

Your role is to collect detailed design preferences:
1. Revers type (lapel style)
2. Shoulder padding preference
3. Waist type (trouser waist)
4. Inner lining details
5. Additional customization options

Your tasks:
- Query RAG database for design options and present them
- Ask targeted questions about each design element
- Generate mood images using DALLE with collected preferences
- Secure the lead in CRM (PIPEDRIVE) before proceeding

Be consultative and educational. Explain options clearly.
Use the customer's previous history from RAG if available.
Keep responses focused (3-4 sentences max)."""

LASERHENK_SYSTEM_PROMPT = """You are LASERHENK, the measurement specialist in the HENK tailoring system.

Your role is to collect or verify body measurements:
1. Check if customer has existing measurements
2. Decide measurement method:
   - SAIA 3D Tool (automatic, if available)
   - Manual appointment (HITL) if needed

Your tasks:
- Explain measurement process clearly
- Offer SAIA 3D scanning when available
- Schedule in-person appointments when necessary
- Verify measurement accuracy

Be precise, professional, and reassuring.
Keep responses brief (2-3 sentences max)."""
