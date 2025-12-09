"""Main Entry Point for HENK Agent System."""

from typing import Optional

from workflow.graph_state import create_initial_state
from workflow.workflow import create_smart_workflow


def create_session(customer_id: Optional[str] = None) -> str:
    """
    Create a new session for customer interaction.

    Args:
        customer_id: Optional existing customer ID

    Returns:
        Session ID
    """
    import uuid

    session_id = str(uuid.uuid4())
    initial_state = create_initial_state(session_id)

    if customer_id:
        initial_state["session_state"].customer.customer_id = customer_id

    return session_id


async def run_agent_system(session_id: str, user_message: str = "Hallo HENK!"):
    """
    Run the HENK agent system for a given session.

    Args:
        session_id: Session identifier

    Executes the LangGraph workflow using the configured nodes.
    """
    print(f"🚀 Starting HENK Agent System for session: {session_id}")

    state = create_initial_state(session_id)
    state["user_input"] = user_message

    workflow = create_smart_workflow()

    final_state = await workflow.ainvoke(state)

    print("🧭 Workflow finished. Messages exchanged:")
    for msg in final_state.get("messages", []):
        sender = msg.get("sender", msg.get("role", "unknown"))
        print(f"  - {sender}: {msg.get('content')}")

    return final_state


def main():
    """Main function."""
    print("=" * 60)
    print("LASERHENK - Agentic AI System")
    print("Version 1.0.0 (Architecture Phase)")
    print("=" * 60)
    print()

    # Create a test session
    session_id = create_session()
    print(f"✅ Session created: {session_id}")
    print()

    # Run the agent system (placeholder)
    import asyncio

    asyncio.run(run_agent_system(session_id))

    print()
    print("=" * 60)
    print("📚 Next Steps:")
    print("  1. Implement LangGraph workflow")
    print("  2. Add LLM integration")
    print("  3. Connect tool APIs")
    print("=" * 60)


if __name__ == "__main__":
    main()
