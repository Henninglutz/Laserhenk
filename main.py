"""Main Entry Point for HENK Agent System."""

import argparse
import asyncio
from typing import Optional, Sequence

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


def parse_cli_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments so users can start a chat directly via main."""

    parser = argparse.ArgumentParser(description="Starte den HENK Chat-Flow")
    parser.add_argument(
        "-m",
        "--message",
        default="Hallo HENK!",
        help="Erste Nutzeranfrage an den Chat",
    )
    parser.add_argument(
        "--customer-id",
        default=None,
        help="Optionaler bestehender Customer-ID für den Flow",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None):
    """Main function to start an interactive chat run."""
    args = parse_cli_args(argv)

    print("=" * 60)
    print("LASERHENK - Agentic AI System")
    print("Version 1.0.0 (Architecture Phase)")
    print("=" * 60)
    print()

    session_id = create_session(customer_id=args.customer_id)
    print(f"✅ Session created: {session_id}")
    if args.customer_id:
        print(f"ℹ️  Existing customer ID injected: {args.customer_id}")
    print(f"💬 Erste Nachricht: {args.message}")
    print()

    asyncio.run(run_agent_system(session_id, user_message=args.message))

    print()
    print("=" * 60)
    print("Flow abgeschlossen")
    print("Starte mit: python main.py --message 'Ich brauche einen Anzug' [--customer-id <ID>]")
    print("=" * 60)


if __name__ == "__main__":
    main()
