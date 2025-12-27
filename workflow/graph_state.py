"""
Graph State Definition für HENK Workflow

Definiert den globalen State, der zwischen allen Nodes geteilt wird.
Typensicher durch TypedDict.
"""

from typing import Annotated, TypedDict, Optional, Dict, Any, List

from langgraph.graph.message import add_messages

from models.customer import Customer, DesignPreferences, SessionState


class HenkGraphState(TypedDict):
    """Zentraler State für den HENK LangGraph Workflow (KISS Variante)."""

    session_state: SessionState
    messages: Annotated[list, add_messages]

    # Routing
    current_agent: str
    awaiting_user_input: bool | None
    is_valid: bool | None

    # Structured next step (serialized Pydantic)
    next_step: dict | None

    # Legacy (optional; kept for compatibility, not used in KISS flow)
    next_agent: Optional[str]
    pending_action: Optional[Dict[str, Any]]
    action_params: Optional[Dict[str, Any]]
    phase_complete: bool

    # Tool outputs (optional legacy)
    rag_output: Optional[Dict[str, Any]]
    crm_output: Optional[Dict[str, Any]]
    dalle_output: Optional[Dict[str, Any]]
    saia_output: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    image_policy: Optional[Dict[str, Any]]


def create_initial_state(session_id: str = "default") -> HenkGraphState:
    """Backward compatible alias for :func:`create_initial_graph_state`."""

    return create_initial_graph_state(session_id=session_id)


def create_initial_graph_state(session_id: str = "default") -> HenkGraphState:
    """Erstellt initialen State für neue Session (KISS Variante)."""

    return HenkGraphState(
        is_valid=None,
        awaiting_user_input=True,
        current_agent="supervisor",
        next_step=None,
        next_agent=None,
        pending_action=None,
        action_params=None,
        phase_complete=False,
        messages=[],
        session_state=SessionState(
            session_id=session_id,
            customer=Customer(),
            design_preferences=DesignPreferences(),
        ),
        rag_output=None,
        crm_output=None,
        dalle_output=None,
        saia_output=None,
        metadata={},
        image_policy=None,
    )
