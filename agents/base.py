"""Base Agent Classes."""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field

from models.customer import SessionState


class AgentDecision(BaseModel):
    """Agent decision output."""

    next_agent: Optional[str] = Field(
        None, description="Next agent to route to"
    )
    message: Optional[str] = Field(
        None, description="Message to user or next agent"
    )
    action: Optional[str] = Field(
        None, description="Action to perform (e.g., 'query_rag', 'create_lead')"
    )
    action_params: Optional[dict] = Field(
        None, description="Parameters for the action"
    )
    should_continue: bool = Field(
        True, description="Whether to continue conversation"
    )


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, agent_name: str):
        """Initialize agent."""
        self.agent_name = agent_name

    @abstractmethod
    async def process(self, state: SessionState) -> AgentDecision:
        """
        Process the current state and return decision.

        Args:
            state: Current session state

        Returns:
            AgentDecision with routing and action information
        """
        pass

    def _update_state(
        self, state: SessionState, **updates
    ) -> SessionState:
        """Helper to update state."""
        updated_data = state.model_dump()
        updated_data.update(updates)
        updated_data["current_agent"] = self.agent_name
        return SessionState(**updated_data)
