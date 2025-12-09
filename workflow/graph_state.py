"""
Graph State Definition für HENK Workflow

Definiert den globalen State, der zwischen allen Nodes geteilt wird.
Typensicher durch TypedDict.
"""

from typing import TypedDict, Optional, Dict, Any, List

from models.customer import Customer, DesignPreferences, SessionState


class HenkGraphState(TypedDict):
    """
    Zentraler State für den gesamten HENK Workflow.

    Wird von LangGraph zwischen allen Nodes weitergereicht und ist
    die einzige Source of Truth für den aktuellen Zustand.

    Attributes:
        user_input: Aktuelle Nachricht vom User
        is_valid: Flag ob Input Validierung bestanden hat
        awaiting_user_input: Wartet System auf User-Response?
        current_agent: Aktuell aktiver Agent/Tool
        next_agent: Vom Supervisor/Agent bestimmter nächster Agent
        pending_action: Parameter für nächste Aktion (z.B. Suchfilter)
        phase_complete: Ist aktuelle Phase (H1/H2/H3) abgeschlossen?
        messages: Komplette Conversation History
        session_state: Session-spezifische Daten (Customer, Phase, etc.)
        metadata: Zusätzliche Metadaten (Reasoning, Confidence, etc.)
    """

    # ==================== User Interaction ====================
    user_input: Optional[str]
    is_valid: bool
    awaiting_user_input: bool

    # ==================== Routing & Orchestration ====================
    current_agent: str
    next_agent: Optional[str]
    pending_action: Optional[Dict[str, Any]]
    phase_complete: bool

    # ==================== Conversation ====================
    messages: List[Dict[str, Any]]

    # ==================== Session Data ====================
    session_state: SessionState

    # ==================== Metadata ====================
    metadata: Dict[str, Any]


def create_initial_state(session_id: str = "default") -> HenkGraphState:
    """
    Erstellt initialen State für neue Session.

    Args:
        session_id: Eindeutige Session ID

    Returns:
        Neuer HenkGraphState mit Default-Werten

    Example:
        >>> state = create_initial_state("user_12345")
        >>> state["session_state"]["session_id"]
        'user_12345'
    """
    return HenkGraphState(
        user_input=None,
        is_valid=False,
        awaiting_user_input=False,
        current_agent="henk1",
        next_agent=None,
        pending_action=None,
        phase_complete=False,
        messages=[],
        session_state=SessionState(
            session_id=session_id,
            customer=Customer(),
            design_preferences=DesignPreferences(),
        ),
        metadata={
            "supervisor_reasoning": None,
            "confidence": 1.0,
            "error_count": 0,
            "total_llm_calls": 0,
        },
    )
