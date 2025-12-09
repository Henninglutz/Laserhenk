#!/usr/bin/env python3
"""
Debug-Script für SupervisorAgent
"""
import asyncio
from agents.supervisor_agent import SupervisorAgent, SupervisorDecision


async def test_supervisor():
    """Test SupervisorAgent mit einfachem Beispiel"""
    print("=" * 60)
    print("Testing SupervisorAgent")
    print("=" * 60)

    # Initialisierung
    print("\n1. Initialisiere SupervisorAgent...")
    supervisor = SupervisorAgent()
    print(f"   ✓ SupervisorAgent erstellt: {supervisor}")
    print(f"   Model: {supervisor.model}")
    print(f"   PydanticAgent: {supervisor.pydantic_agent}")

    # Test 1: Einfache Entscheidung
    print("\n2. Test: decide_next_step()...")
    try:
        decision = await supervisor.decide_next_step(
            user_message="Zeig mir Wollstoffe",
            session_state={
                "current_phase": "H2",
                "customer_data": {}
            },
            conversation_history=[]
        )

        print(f"   ✓ Decision erhalten:")
        print(f"     next_destination: {decision.next_destination}")
        print(f"     reasoning: {decision.reasoning}")
        print(f"     action_params: {decision.action_params}")
        print(f"     confidence: {decision.confidence}")

    except AttributeError as e:
        print(f"   ✗ AttributeError: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"   ✗ Exception: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Prüfe SupervisorDecision Struktur
    print("\n3. Test: SupervisorDecision Objekt...")
    try:
        decision = SupervisorDecision(
            next_destination="rag_tool",
            reasoning="User wants to see fabrics",
            action_params={"fabric_type": "wool"},
            confidence=0.9
        )
        print(f"   ✓ SupervisorDecision erstellt:")
        print(f"     {decision}")

    except Exception as e:
        print(f"   ✗ Exception: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Tests abgeschlossen")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_supervisor())
