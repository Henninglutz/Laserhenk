"""
Workflow Package für HENK Multi-Agent System

Enthält State Definition, Node Functions und Workflow Assembly.
"""

from .graph_state import HenkGraphState, create_initial_state
from .workflow import create_smart_workflow

__all__ = ["HenkGraphState", "create_initial_state", "create_workflow", "create_smart_workflow"]


def create_workflow():
    """
    Erstellt den Workflow für HENK Multi-Agent System.

    Wrapper für create_smart_workflow() für Rückwärtskompatibilität.

    Returns:
        Kompilierter StateGraph ready für Execution
    """
    return create_smart_workflow()