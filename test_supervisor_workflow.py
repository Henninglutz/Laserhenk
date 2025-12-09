#!/usr/bin/env python3
"""
Vollständiger Workflow-Test mit SupervisorAgent
"""
import asyncio
from workflow.graph_state import create_initial_state
from workflow import create_workflow


async def test_workflow_with_input():
    """Test Workflow mit echtem User-Input"""
    print("=" * 80)
    print("TESTING WORKFLOW WITH SUPERVISOR AGENT")
    print("=" * 80)

    # Create initial state
    session_id = "test_session_123"
    initial_state = create_initial_state(session_id)

    # Set user input
    initial_state["user_input"] = "Ich brauche einen Anzug für eine Hochzeit"

    print(f"\nSession ID: {session_id}")
    print(f"User Input: {initial_state['user_input']}")
    print()

    # Create workflow
    print("Creating workflow...")
    workflow = create_workflow()
    print("✓ Workflow created successfully")
    print()

    # Run workflow
    print("Starting workflow execution...")
    print("=" * 80)

    try:
        step_count = 0
        max_steps = 5

        async for event in workflow.astream(initial_state):
            step_count += 1
            print()
            print(f"STEP {step_count}")
            print("=" * 40)

            for node_name, node_state in event.items():
                print(f"\nNode: {node_name}")
                print(f"  current_agent: {node_state.get('current_agent')}")
                print(f"  next_agent: {node_state.get('next_agent')}")
                print(f"  is_valid: {node_state.get('is_valid')}")
                print(f"  awaiting_user_input: {node_state.get('awaiting_user_input')}")

                # Check for messages
                if 'messages' in node_state:
                    messages = node_state.get('messages', [])
                    if messages:
                        last_msg = messages[-1]
                        print(f"  Last message: {last_msg.get('content', '')[:100]}...")

                # Check metadata
                if 'metadata' in node_state:
                    metadata = node_state.get('metadata', {})
                    if metadata.get('supervisor_reasoning'):
                        print(f"  Supervisor reasoning: {metadata['supervisor_reasoning']}")
                        print(f"  Confidence: {metadata.get('confidence', 'N/A')}")

            if step_count >= max_steps:
                print()
                print("⚠️  Max steps reached")
                break

        print()
        print("=" * 80)
        print(f"✓ WORKFLOW COMPLETED SUCCESSFULLY")
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
    asyncio.run(test_workflow_with_input())
