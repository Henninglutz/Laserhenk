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
                next_agent="operator",
                message="Using existing measurements",
                action="retrieve_measurements",
                action_params={"customer_id": state.customer.customer_id},
                should_continue=True,
            )

        # Option 1: SAIA 3D measurement (wenn verfügbar)
        # Option 2: HITL - Schedule appointment
        # Für MVP: Entscheidung basiert auf Verfügbarkeit

        # Placeholder: Request SAIA measurement
        if not state.measurements:
            return AgentDecision(
                next_agent="laserhenk",
                message="Requesting 3D measurement via SAIA",
                action="request_saia_measurement",
                action_params={
                    "customer_id": state.customer.customer_id,
                    "scan_type": "full_body",
                },
                should_continue=True,
            )

        # Measurements complete → route to operator
        return AgentDecision(
            next_agent="operator",
            message="Measurements complete",
            action="complete_measurement_phase",
            should_continue=True,
        )
