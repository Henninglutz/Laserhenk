"""LangGraph State Models."""

from typing import Annotated, TypedDict

from langgraph.graph import add_messages

from models.customer import (
    Customer,
    DesignPreferences,
    SessionState,
)


class HenkGraphState(TypedDict):
    """
    LangGraph State für HENK Agent System.

    LangGraph verwendet TypedDict für State Management.
    Diese Klasse wrapped unseren SessionState für LangGraph.
    """

    # Core state
    session_state: SessionState

    # Messages (LangGraph managed)
    messages: Annotated[list, add_messages]

    # Current routing
    current_agent: str
    next_agent: str | None

    # Action tracking
    pending_action: str | None
    action_params: dict | None

    # Tool outputs (temporary storage)
    rag_output: dict | None
    crm_output: dict | None
    dalle_output: dict | None
    saia_output: dict | None


def create_initial_graph_state(session_id: str) -> HenkGraphState:
    """
    Create initial graph state for new session.

    Args:
        session_id: Unique session identifier

    Returns:
        Initial HenkGraphState
    """
    initial_session = SessionState(
        session_id=session_id,
        customer=Customer(),
        design_preferences=DesignPreferences(),
    )

    return HenkGraphState(
        session_state=initial_session,
        messages=[],
        current_agent="operator",
        next_agent=None,
        pending_action=None,
        action_params=None,
        rag_output=None,
        crm_output=None,
        dalle_output=None,
        saia_output=None,
    )
