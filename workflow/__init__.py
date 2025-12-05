"""
Workflow Package für HENK Multi-Agent System

Enthält State Definition, Node Functions und Workflow Assembly.
"""

from .graph_state import HenkGraphState, create_initial_state

__all__ = ["HenkGraphState", "create_initial_state"]
