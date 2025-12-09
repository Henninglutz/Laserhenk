import asyncio
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main


def test_run_agent_system_executes_workflow(monkeypatch):
    """Run the LangGraph workflow end-to-end using the offline fallback."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    session_id = "test-session"

    final_state = asyncio.run(
        main.run_agent_system(
            session_id, user_message="Ich brauche einen maßgeschneiderten Anzug"
        )
    )

    messages = final_state.get("messages", [])

    assert any(msg.get("sender") == "henk1" for msg in messages)
    assert any(msg.get("sender") == "design_henk" for msg in messages)
    assert any(msg.get("sender") == "laserhenk" for msg in messages)

    session_state = final_state["session_state"]
    assert session_state.customer.customer_id is not None
    assert session_state.design_preferences.revers_type is not None
    assert session_state.measurements is not None
