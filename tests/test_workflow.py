"""Test script to debug the RAG infinite loop issue."""

import asyncio
import sys
import uuid
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


from workflow.graph_state import create_initial_state
from workflow import create_workflow


@pytest.mark.skip(reason="Manueller Debug-Flow, für lokale Integrationstests reserviert")
async def test_workflow():
    """Test the workflow to identify the infinite loop issue."""
    print("=" * 80)
    print("TESTING HENK WORKFLOW - DEBUGGING RAG INFINITE LOOP")
    print("=" * 80)
    print()

    # Create initial state
    session_id = str(uuid.uuid4())
    initial_state = create_initial_state(session_id)

    print(f"Session ID: {session_id}")
    print("Initial state created")
    print(f"Initial rag_context: {initial_state['session_state'].rag_context}")
    print()

    # Create workflow
    print("Creating workflow...")
    workflow = create_workflow()
    print("Workflow created successfully")
    print()

    # Run workflow with a max of 10 steps to prevent infinite loop
    print("Starting workflow execution...")
    print("=" * 80)
    print()

    try:
        step_count = 0
        max_steps = 10

        async for event in workflow.astream(initial_state):
            step_count += 1
            print()
            print(f"{'=' * 80}")
            print(f"STEP {step_count}")
            print(f"{'=' * 80}")
            print(f"Event keys: {event.keys()}")

            # Print current state
            for node_name, node_state in event.items():
                print(f"\nNode: {node_name}")
                print(f"  current_agent: {node_state.get('current_agent')}")
                print(f"  next_agent: {node_state.get('next_agent')}")
                print(f"  pending_action: {node_state.get('pending_action')}")

                # Session state may not be present in all nodes
                if 'session_state' in node_state:
                    session_state = node_state['session_state']
                    print(f"  rag_context: {session_state.rag_context}")
                    print(f"  customer_id: {session_state.customer.customer_id}")
                else:
                    print("  session_state: Not present in this node output")

            if step_count >= max_steps:
                print()
                print("=" * 80)
                print(f"⚠️  STOPPED AFTER {max_steps} STEPS TO PREVENT INFINITE LOOP")
                print("=" * 80)
                break

        print()
        print("=" * 80)
        print("WORKFLOW EXECUTION COMPLETED")
        print(f"Total steps: {step_count}")
        print("=" * 80)

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ERROR: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_workflow())
