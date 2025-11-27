"""Main Entry Point for HENK Agent System."""

from typing import Optional

from models.graph_state import create_initial_graph_state
from workflow.graph import create_henk_graph, run_henk_workflow, resume_henk_workflow


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
    """
    print(f"Starting HENK Agent System (Session: {session_id})")

    # Create and execute graph
    graph = create_henk_graph()
    print(f"Graph initialized: {len(graph.nodes)} nodes")

    initial_state = create_initial_graph_state(session_id)

    # Execute workflow
    final_state = await run_henk_workflow(
        initial_state=initial_state,
        thread_id=session_id
    )

    print(f"Workflow complete. Final agent: {final_state.get('current_agent')}")
    return final_state


def main():
    """Main function."""
    import asyncio

    print("=" * 60)
    print("LASERHENK - Agentic AI System")
    print("=" * 60)

    session_id = create_session()
    asyncio.run(run_agent_system(session_id))


if __name__ == "__main__":
    main()
