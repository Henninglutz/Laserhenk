"""Tests für Fabric-Präferenz-Parsing."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.customer import Customer, SessionState
from tools.fabric_preferences import build_fabric_search_criteria


def _empty_state() -> SessionState:
    return SessionState(session_id="s1", customer=Customer())


def test_negation_excludes_color_and_keeps_explicit_choice():
    query = "ja, nur mit rot, nicht mit blau, bitte weniger uhren"
    params = {"color": "Red"}

    criteria, _, excluded, _ = build_fabric_search_criteria(query, params, _empty_state())

    assert criteria.colors == ["red"]
    assert excluded == ["blue"]


def test_extracts_red_from_german_query():
    query = "bitte einen roten stoff zeigen"
    params = {}

    criteria, _, excluded, _ = build_fabric_search_criteria(query, params, _empty_state())

    assert criteria.colors == ["red"]
    assert excluded == []


def test_negation_patterns_block_color_matches():
    query = "ohne blau, eher weinrot"
    params = {}

    criteria, _, excluded, _ = build_fabric_search_criteria(query, params, _empty_state())

    assert "blue" not in criteria.colors
    assert "burgundy" in criteria.colors
    assert "blue" in excluded
