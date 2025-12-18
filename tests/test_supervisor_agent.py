import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.supervisor_agent import SupervisorAgent
from models.customer import Customer, SessionState


def make_state(**kwargs):
    base = dict(
        session_id="test-session",
        customer=Customer(),
    )
    base.update(kwargs)
    return SessionState(**base)


def test_pre_route_design_keywords_route_to_design_henk_when_fabric_selected():
    agent = SupervisorAgent()
    state = make_state(
        shown_fabric_images=[{"fabric_code": "X"}],
        favorite_fabric={"fabric_code": "X"},
    )

    decision = agent._pre_route("stegrevers und wenig polster", state)

    assert decision is not None
    assert decision.next_destination == "design_henk"
    assert decision.user_message == "stegrevers und wenig polster"


def test_pre_route_ignores_design_keywords_without_design_phase():
    agent = SupervisorAgent()
    state = make_state()

    decision = agent._pre_route("stegrevers und wenig polster", state)

    assert decision is None


@pytest.mark.parametrize(
    "message",
    [
        "der dritte bitte",
        "nummer 3 bitte",
        "#3 passt",
    ],
)
def test_pre_route_accepts_third_fabric_selection(message):
    agent = SupervisorAgent()
    state = make_state(shown_fabric_images=[{"fabric_code": "A"}] * 3)

    decision = agent._pre_route(message, state)

    assert decision is not None
    assert decision.next_destination == "henk1"


@pytest.mark.parametrize(
    "message, expected_index",
    [
        ("34m1000 der bitte", 0),
        ("der rechte Stoff", 1),
    ],
)
def test_pre_route_accepts_fabric_codes_and_positions(message, expected_index):
    agent = SupervisorAgent()
    state = make_state(
        shown_fabric_images=[
            {"fabric_code": "34M1000"},
            {"fabric_code": "98T1027"},
        ]
    )

    decision = agent._pre_route(message, state)

    assert decision is not None
    assert decision.next_destination == "henk1"
