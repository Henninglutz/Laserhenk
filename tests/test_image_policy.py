"""Tests for image policy routing and DALL-E gating."""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.image_policy import ImagePolicyAgent
from models.customer import Customer, DesignPreferences, SessionState
from models.api_payload import ImagePolicyDecision
from models.tools import DALLEImageRequest
from tools.dalle_tool import DALLETool


@pytest.mark.asyncio
async def test_image_policy_prefers_rag_images():
    state = SessionState(
        session_id="test",
        customer=Customer(),
        design_preferences=DesignPreferences(),
    )
    state.rag_context = {
        "fabrics": [
            {
                "fabric_code": "ABC123",
                "image_urls": ["/fabrics/images/ABC123.jpg"],
            }
        ]
    }

    decision = await ImagePolicyAgent().decide(
        user_message="Bitte zeig mir ein Moodboard.",
        state=state,
        supervisor_allows_dalle=True,
    )

    assert decision.allowed_source == "rag"


@pytest.mark.asyncio
async def test_image_policy_blocks_without_images():
    state = SessionState(
        session_id="test",
        customer=Customer(),
        design_preferences=DesignPreferences(),
    )

    decision = await ImagePolicyAgent().decide(
        user_message="Zeig mir bitte ein Moodboard.",
        state=state,
        supervisor_allows_dalle=True,
    )

    assert decision.allowed_source == "none"


@pytest.mark.asyncio
async def test_image_policy_allows_dalle_with_explicit_opt_in(monkeypatch):
    state = SessionState(
        session_id="test",
        customer=Customer(),
        design_preferences=DesignPreferences(),
    )

    monkeypatch.setenv("ENABLE_DALLE", "true")

    decision = await ImagePolicyAgent().decide(
        user_message="Bitte erstelle ein illustrative moodboard.",
        state=state,
        supervisor_allows_dalle=True,
    )

    assert decision.allowed_source == "dalle"


@pytest.mark.asyncio
async def test_dalle_tool_refuses_without_dalle_policy():
    decision = ImagePolicyDecision(
        want_images=True,
        allowed_source="rag",
        rationale="RAG images available",
        required_fabric_images=True,
        max_images=2,
    )

    response = await DALLETool().generate_image(
        request=DALLEImageRequest(prompt="test"),
        decision=decision,
    )

    assert response.success is False
    assert response.policy_blocked is True
