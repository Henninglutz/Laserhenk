"""Main Entry Point for HENK Agent System."""

from typing import Optional

from agents.operator import OperatorAgent
from models.customer import Customer
from models.graph_state import create_initial_graph_state


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
    initial_state = create_initial_graph_state(session_id)

    if customer_id:
        initial_state["session_state"].customer.customer_id = customer_id

    return session_id


async def run_agent_system(session_id: str):
    """
    Run the HENK agent system for a given session.

    Args:
        session_id: Session identifier

    This is a placeholder for the actual LangGraph workflow.
    In Phase 2, this will be replaced with proper LangGraph execution.
    """
    print(f"🚀 Starting HENK Agent System for session: {session_id}")
    print("⚠️  Note: This is an architecture placeholder.")
    print("📋 LangGraph workflow execution will be implemented in Phase 2.")

    # Placeholder: Initialize operator
    operator = OperatorAgent()
    print(f"✅ Operator Agent initialized: {operator.agent_name}")

    # TODO: Phase 2
    # - Initialize LangGraph StateGraph
    # - Add agent nodes
    # - Define edges and conditional routing
    # - Execute workflow


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
