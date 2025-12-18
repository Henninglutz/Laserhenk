import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.henk1 import Henk1Agent


def test_detects_fabric_code_selection():
    agent = Henk1Agent()
    fabrics = [
        {"fabric_code": "34M1000"},
        {"fabric_code": "98T1027"},
    ]

    choice = agent._detect_fabric_choice("34m1000 der bitte", fabrics)

    assert choice == 0


def test_detects_right_position_selection():
    agent = Henk1Agent()
    fabrics = [{"fabric_code": "X"}, {"fabric_code": "Y"}]

    choice = agent._detect_fabric_choice("der rechte", fabrics)

    assert choice == 1
