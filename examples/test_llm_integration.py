"""Test LLM Integration - GPT-4 Enhanced Agents.

This script demonstrates how to use GPT-4 enhanced decision-making
in the HENK agent system.

Requirements:
1. Set OPENAI_API_KEY in .env file
2. Ensure openai package is installed
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_service import (
    LLMService,
    HENK1_SYSTEM_PROMPT,
    DESIGN_HENK_SYSTEM_PROMPT,
    LASERHENK_SYSTEM_PROMPT,
    OPERATOR_SYSTEM_PROMPT,
)


async def test_basic_llm():
    """Test basic LLM functionality."""
    print("=" * 60)
    print("Testing Basic LLM Integration")
    print("=" * 60)
    print()

    try:
        llm = LLMService()
        print("✅ LLM Service initialized successfully")
        print(f"   Model: {llm.model}")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize LLM Service: {e}")
        print("   Make sure OPENAI_API_KEY is set in .env")
        return

    # Test conversational response
    print("Testing conversational response...")
    print("-" * 60)

    response = await llm.generate_response(
        system_prompt="You are a helpful assistant.",
        user_message="Say hello in German.",
        temperature=0.7,
        max_tokens=50,
    )

    print(f"Response: {response}")
    print()


async def test_henk1_agent():
    """Test HENK1 agent with LLM."""
    print("=" * 60)
    print("Testing HENK1 Agent (Needs Assessment)")
    print("=" * 60)
    print()

    try:
        llm = LLMService()
    except Exception as e:
        print(f"❌ LLM not available: {e}")
        return

    # Simulate customer interaction
    customer_context = {
        "customer_type": "new",
        "session_id": "test_123",
    }

    user_message = """
    New customer just entered the store.
    They mentioned they need a suit for a wedding next month.
    Greet them warmly and begin needs assessment.
    """

    print("Context:", customer_context)
    print("Scenario:", user_message.strip())
    print()
    print("HENK1 Response:")
    print("-" * 60)

    response = await llm.generate_response(
        system_prompt=HENK1_SYSTEM_PROMPT,
        user_message=user_message,
        context=customer_context,
        temperature=0.8,
        max_tokens=200,
    )

    print(response)
    print()


async def test_design_henk_agent():
    """Test Design HENK agent with LLM."""
    print("=" * 60)
    print("Testing Design HENK Agent (Preferences)")
    print("=" * 60)
    print()

    try:
        llm = LLMService()
    except Exception as e:
        print(f"❌ LLM not available: {e}")
        return

    customer_context = {
        "customer_id": "CUST_123",
        "occasion": "wedding",
        "style_preference": "classic",
    }

    user_message = """
    Customer has completed needs assessment.
    Ask about design preferences:
    - Lapel style (revers)
    - Shoulder padding
    - Inner lining
    Start with asking about lapel style.
    """

    print("Context:", customer_context)
    print("Scenario:", user_message.strip())
    print()
    print("Design HENK Response:")
    print("-" * 60)

    response = await llm.generate_response(
        system_prompt=DESIGN_HENK_SYSTEM_PROMPT,
        user_message=user_message,
        context=customer_context,
        temperature=0.7,
        max_tokens=200,
    )

    print(response)
    print()


async def test_laserhenk_agent():
    """Test LASERHENK agent with LLM."""
    print("=" * 60)
    print("Testing LASERHENK Agent (Measurements)")
    print("=" * 60)
    print()

    try:
        llm = LLMService()
    except Exception as e:
        print(f"❌ LLM not available: {e}")
        return

    customer_context = {
        "customer_id": "CUST_123",
        "design_complete": True,
        "saia_available": True,
    }

    user_message = """
    Customer has finalized design preferences.
    Offer SAIA 3D measurement option.
    Explain the benefits of 3D scanning.
    """

    print("Context:", customer_context)
    print("Scenario:", user_message.strip())
    print()
    print("LASERHENK Response:")
    print("-" * 60)

    response = await llm.generate_response(
        system_prompt=LASERHENK_SYSTEM_PROMPT,
        user_message=user_message,
        context=customer_context,
        temperature=0.7,
        max_tokens=150,
    )

    print(response)
    print()


async def main():
    """Run all LLM integration tests."""
    print()
    print("🚀 HENK LLM Integration Test Suite")
    print()

    # Test basic functionality
    await test_basic_llm()

    # Test agent-specific prompts
    await test_henk1_agent()
    await test_design_henk_agent()
    await test_laserhenk_agent()

    print("=" * 60)
    print("✅ All LLM Integration Tests Complete")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("  1. Agents are using GPT-4 for intelligent decision-making")
    print("  2. System prompts are loaded for each agent type")
    print("  3. Falls back gracefully to state-based logic if API unavailable")
    print()


if __name__ == "__main__":
    asyncio.run(main())
