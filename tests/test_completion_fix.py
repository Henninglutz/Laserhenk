"""Test completion detection logic in SupervisorAgent rule-based routing."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.supervisor_agent import SupervisorAgent


def test_rule_based_routing_prevents_henk1_loop():
    """Test that rule-based routing doesn't route back to henk1 when already complete."""
    supervisor = SupervisorAgent()

    # Simulate session where HENK1 already completed
    session_state = {
        "current_phase": "H1",
        "henk1_rag_queried": True,  # HENK1 already queried RAG
        "design_rag_queried": False,
        "henk1_to_design_payload": None,
        "customer_data": {"budget": 2000, "occasion": "wedding"}
    }

    conversation_history = [
        {"role": "user", "content": "Ich brauche einen Anzug", "sender": "user"},
        {"role": "assistant", "content": "Gerne! Hier sind passende Stoffe...", "sender": "henk1"},
    ]

    # Generic user message (no specific keywords)
    user_message = "Ok, gut"

    decision = supervisor._rule_based_routing(user_message, session_state, conversation_history)

    print(f"✓ Test 1: HENK1 complete with response")
    print(f"  Input: '{user_message}'")
    print(f"  henk1_rag_queried: True")
    print(f"  Decision: {decision.next_destination}")
    print(f"  Reasoning: {decision.reasoning}")

    # Should NOT route back to henk1
    assert decision.next_destination != "henk1", \
        f"Expected NOT 'henk1', got '{decision.next_destination}' - INFINITE LOOP DETECTED!"

    # Should route to design_henk or end
    assert decision.next_destination in ["design_henk", "end"], \
        f"Expected 'design_henk' or 'end', got '{decision.next_destination}'"

    print(f"  ✅ PASS: Routes to {decision.next_destination}, avoiding loop!\n")


def test_rule_based_routing_without_completion():
    """Test that rule-based routing DOES route to henk1 when NOT complete."""
    supervisor = SupervisorAgent()

    # Simulate fresh session where HENK1 NOT complete
    session_state = {
        "current_phase": "H0",
        "henk1_rag_queried": False,  # NOT complete
        "design_rag_queried": False,
        "customer_data": {}
    }

    conversation_history = []

    # Generic user message (no specific keywords)
    user_message = "Hallo"

    decision = supervisor._rule_based_routing(user_message, session_state, conversation_history)

    print(f"✓ Test 2: HENK1 NOT complete (first visit)")
    print(f"  Input: '{user_message}'")
    print(f"  henk1_rag_queried: False")
    print(f"  Decision: {decision.next_destination}")
    print(f"  Reasoning: {decision.reasoning}")

    # SHOULD route to henk1
    assert decision.next_destination == "henk1", \
        f"Expected 'henk1', got '{decision.next_destination}'"

    print(f"  ✅ PASS: Correctly routes to henk1 on first visit!\n")


def test_rule_based_routing_fabric_query_priority():
    """Test that fabric queries always route to rag_tool, even if henk1 complete."""
    supervisor = SupervisorAgent()

    # HENK1 complete, but user asks for fabrics
    session_state = {
        "current_phase": "H1",
        "henk1_rag_queried": True,
        "design_rag_queried": False,
    }

    conversation_history = [
        {"role": "assistant", "content": "Bereits beantwortet", "sender": "henk1"},
    ]

    # Fabric query
    user_message = "Zeig mir mehr Stoffe"

    decision = supervisor._rule_based_routing(user_message, session_state, conversation_history)

    print(f"✓ Test 3: Fabric query with HENK1 complete")
    print(f"  Input: '{user_message}'")
    print(f"  Decision: {decision.next_destination}")
    print(f"  Reasoning: {decision.reasoning}")

    # Should route to rag_tool
    assert decision.next_destination == "rag_tool", \
        f"Expected 'rag_tool', got '{decision.next_destination}'"

    print(f"  ✅ PASS: Fabric queries have priority!\n")


def test_rule_based_routing_end_keywords():
    """Test that end keywords route to 'end' destination."""
    supervisor = SupervisorAgent()

    session_state = {
        "current_phase": "H1",
        "henk1_rag_queried": True,
    }

    conversation_history = []

    # End keyword
    user_message = "Danke, das war's"

    decision = supervisor._rule_based_routing(user_message, session_state, conversation_history)

    print(f"✓ Test 4: End keyword detection")
    print(f"  Input: '{user_message}'")
    print(f"  Decision: {decision.next_destination}")
    print(f"  Reasoning: {decision.reasoning}")

    # Should route to end
    assert decision.next_destination == "end", \
        f"Expected 'end', got '{decision.next_destination}'"

    print(f"  ✅ PASS: End keywords detected!\n")


if __name__ == "__main__":
    print("=" * 80)
    print("TESTING COMPLETION DETECTION FIX FOR INFINITE LOOP")
    print("=" * 80)
    print()

    try:
        test_rule_based_routing_prevents_henk1_loop()
        test_rule_based_routing_without_completion()
        test_rule_based_routing_fabric_query_priority()
        test_rule_based_routing_end_keywords()

        print("=" * 80)
        print("✅ ALL TESTS PASSED - Infinite loop fix working correctly!")
        print("=" * 80)

    except AssertionError as e:
        print("=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        sys.exit(1)
    except Exception as e:
        print("=" * 80)
        print(f"❌ ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)
