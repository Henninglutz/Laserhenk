"""Operator Agent - Routes to specialized agents."""

from typing import Optional

from agents.base import AgentDecision, BaseAgent
from models.customer import CustomerType, SessionState


class OperatorAgent(BaseAgent):
    """
    Operator Agent.

    Entscheidet, welcher spezialisierte Agent (HENK1, Design HENK, LASERHENK)
    als nächstes aktiv wird basierend auf dem aktuellen SessionState.
    """

    def __init__(self):
        """Initialize Operator Agent."""
        super().__init__("operator")

    async def process(self, state: SessionState) -> AgentDecision:
        """
        Route to appropriate specialized agent.

        Logik:
        1. Wenn neu → HENK1 (Bedarfsermittlung)
        2. Wenn Bedarf ermittelt → Design HENK (Präferenzen + Leadsicherung)
        3. Wenn Design abgeschlossen → LASERHENK (Maße)
        """
        # Start: HENK1 für Bedarfsermittlung
        if not state.customer.customer_id:
            return AgentDecision(
                next_agent="henk1",
                message="Routing to HENK1 for needs assessment",
                action="start_conversation",
                should_continue=True,
            )

        # Design Phase: Design HENK
        if (
            state.customer.customer_id
            and not state.design_preferences.revers_type
        ):
            return AgentDecision(
                next_agent="design_henk",
                message="Routing to Design HENK for design preferences",
                action="collect_preferences",
                should_continue=True,
            )

        # Measurement Phase: LASERHENK
        if (
            state.design_preferences.revers_type
            and not state.measurements
        ):
            return AgentDecision(
                next_agent="laserhenk",
                message="Routing to LASERHENK for measurements",
                action="collect_measurements",
                should_continue=True,
            )

        # All done
        return AgentDecision(
            next_agent=None,
            message="Process complete",
            action="finalize",
            should_continue=False,
        )
