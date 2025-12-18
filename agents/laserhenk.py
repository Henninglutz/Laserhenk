"""LASERHENK Agent - Maßerfassung (SAIA 3D / HITL)."""

from agents.base import AgentDecision, BaseAgent
from models.customer import SessionState


class LaserHenkAgent(BaseAgent):
    """
    LASERHENK - Maßerfassung Agent.

    Aufgaben:
    - Maße über SAIA 3D Tool erfassen ODER
    - Human-in-the-Loop (HITL): Termin beim Kunden vereinbaren
    """

    def __init__(self):
        """Initialize LASERHENK Agent."""
        super().__init__("laserhenk")

    async def process(self, state: SessionState) -> AgentDecision:
        """
        Process measurement collection.

        Returns:
            AgentDecision with next steps
        """
        # Hier würde die Logik für Maßerfassung stehen
        # Für jetzt: Struktur-Placeholder

        # Check if customer has existing measurements
        if state.customer.has_measurements:
            return AgentDecision(
                next_agent=None,
                message="Using existing measurements",
                action="retrieve_measurements",
                action_params={"customer_id": state.customer.customer_id},
                should_continue=False,
            )

        # Option 1: SAIA 3D measurement (wenn verfügbar)
        # Option 2: HITL - Schedule appointment
        # Für MVP: Entscheidung basiert auf Verfügbarkeit

        # Placeholder: Request SAIA measurement
        if not state.measurements:
            # FIX: Stop infinite loop - wait for user input or tool execution
            # TODO: Implement SAIA measurement tool in TOOL_REGISTRY
            return AgentDecision(
                next_agent=None,
                message="Um mit der Maßerfassung fortzufahren, benötigen wir ein 3D-Scan. Bitte kontaktiere uns für einen Termin.",
                action=None,
                action_params=None,
                should_continue=False,  # FIXED: Was True, causing infinite loop
            )

        # Measurements complete → hand back to supervisor
        return AgentDecision(
            next_agent=None,
            message="Measurements complete",
            action="complete_measurement_phase",
            should_continue=False,
        )
