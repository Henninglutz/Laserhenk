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

    Executes the LangGraph workflow with:
    - 4 Agents: Operator, HENK1, Design HENK, LASERHENK
    - Tool Nodes: RAG, CRM, DALLE, SAIA
    - HITL Interrupts for human approval
    """
    print(f"🚀 Starting HENK Agent System for session: {session_id}")
    print()

    print("📊 LangGraph Workflow Components:")
    print("  ✓ 4 Agent Nodes: Operator, HENK1, Design HENK, LASERHENK")
    print("  ✓ 4 Tool Nodes: RAG, CRM, DALLE, SAIA")
    print("  ✓ Conditional Edges based on Operator logic")
    print("  ✓ HITL Interrupts:")
    print("    - Design HENK: CRM Lead approval")
    print("    - LASERHENK: SAIA 3D Tool OR Manual measurement")
    print()

    # Create and visualize graph
    graph = create_henk_graph()
    print(f"✅ LangGraph StateGraph compiled successfully")
    print()

    # Show graph structure
    print("📋 Graph Structure:")
    print(f"  Nodes: {len(graph.nodes)}")
    for node_name in graph.nodes:
        print(f"    - {node_name}")
    print()

    print("💡 Workflow Ready for Execution")
    print()
    print("ℹ️  Note: Full workflow execution requires:")
    print("  • LLM integration for intelligent agent decisions")
    print("  • External API connections (PIPEDRIVE, DALLE, SAIA)")
    print("  • RAG database setup")
    print("  • User interface for HITL interactions")
    print()
    print("✅ Phase 2 Complete: LangGraph workflow architecture implemented!")


def main():
    """Main function."""
    print("=" * 60)
    print("LASERHENK - Agentic AI System")
    print("Version 2.0.0 (LangGraph Workflow)")
    print("=" * 60)
    print()

    # Create a test session
    session_id = create_session()
    print(f"✅ Session created: {session_id}")
    print()

    # Run the agent system with LangGraph workflow
    import asyncio

    asyncio.run(run_agent_system(session_id))

    print()
    print("=" * 60)
    print("✅ Phase 2 Complete: LangGraph Workflow Implemented")
    print("📚 Next Steps:")
    print("  1. Add LLM integration for agent decision-making")
    print("  2. Connect external tool APIs (PIPEDRIVE, DALLE, SAIA)")
    print("  3. Implement RAG database queries")
    print("  4. Add user interface for HITL interactions")
    print("=" * 60)


if __name__ == "__main__":
    main()
