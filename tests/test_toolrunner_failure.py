import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.customer import Customer, SessionState
from workflow.nodes_kiss import HandoffAction, ToolResult, TOOL_REGISTRY, _run_tool_action


@pytest.mark.asyncio
async def test_toolrunner_stops_after_first_image_failure(monkeypatch):
    state = {"session_state": SessionState(session_id="s1", customer=Customer())}

    async def failing_tool(params, state):  # pragma: no cover - simple stub
        return ToolResult(text="fail", metadata={"success": False, "error": "boom"})

    monkeypatch.setitem(TOOL_REGISTRY, "dalle_tool", failing_tool)
    action = HandoffAction(
        kind="tool", name="dalle_tool", params={}, should_continue=True, return_to_agent="design_henk"
    )

    result = await _run_tool_action(action, state)
    session = result["session_state"]

    assert session.image_generation_failed is True
    assert session.last_tool_error == "boom"
    assert result["awaiting_user_input"] is True
    assert result["next_step"] is None or result["next_step"].get("should_continue") is False
