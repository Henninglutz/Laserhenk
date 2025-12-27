import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.customer import Customer, SessionState
from tools.fabric_preferences import build_fabric_search_criteria


def _state() -> SessionState:
    return SessionState(session_id="s2", customer=Customer())


def test_alternative_fabrics_injects_material_and_pattern_variation():
    query = "andere Stoffe bitte"
    criteria, _, _, _ = build_fabric_search_criteria(query, {}, _state())

    assert criteria.preferred_materials == ["wool"]
    assert criteria.patterns == ["twill"]


def test_alternative_respects_explicit_material():
    query = "andere stoffe aus kaschmir bitte"
    params = {"materials": ["cashmere"]}
    criteria, _, _, _ = build_fabric_search_criteria(query, params, _state())

    assert criteria.preferred_materials == ["cashmere"]
    # Trotzdem Variation bei Muster erzwingen
    assert "twill" in criteria.patterns
