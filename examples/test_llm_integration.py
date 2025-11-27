"""Test LLM Integration - GPT-4 Enhanced Agents.

This script demonstrates how to use GPT-4 enhanced decision-making
in the HENK agent system.

Requirements:
1. Set OPENAI_API_KEY in .env file
2. System prompts loaded from Google Drive
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm_service import LLMService, PromptLoader


async def test_basic_llm():
    """Test basic LLM functionality."""
    print("=" * 60)
    print("Testing Basic LLM Integration")
    print("=" * 60)
    print()

    try:
        llm = LLMService()
        print("✅ LLM Service initialized")
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


async def test_prompt_loader():
    """Test prompt loading from Google Drive."""
    print("=" * 60)
    print("Testing Prompt Loader")
    print("=" * 60)
    print()

    try:
        loader = PromptLoader()
        print("✅ PromptLoader initialized")
        print()

        # Load all prompts
        prompts = await loader.load_all_prompts()

        print("Loaded prompts for agents:")
        for agent_name, prompt in prompts.items():
            print(f"  • {agent_name}: {len(prompt)} chars")

        print()
    except Exception as e:
        print(f"❌ Failed to load prompts: {e}")
        print()


async def test_agent_with_custom_prompt():
    """Test agent with custom prompt."""
    print("=" * 60)
    print("Testing Agent with Custom Prompt")
    print("=" * 60)
    print()

    try:
        llm = LLMService()
    except Exception as e:
        print(f"❌ LLM not available: {e}")
        return

    # Example: HENK1 needs assessment
    custom_prompt = """You are HENK1, a tailoring needs assessment specialist.

Your role:
- Greet customers warmly
- Understand their tailoring needs
- Ask about occasion, style preferences
- Be concise (2-3 sentences max)
"""

    customer_context = {
        "customer_type": "new",
        "session_id": "test_123",
    }

    user_message = "New customer needs a suit for a wedding next month."

    print("Custom Prompt:", custom_prompt[:100] + "...")
    print("Scenario:", user_message)
    print()
    print("Response:")
    print("-" * 60)

    response = await llm.generate_response(
        system_prompt=custom_prompt,
        user_message=user_message,
        context=customer_context,
        temperature=0.8,
        max_tokens=200,
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

    # Test prompt loader
    await test_prompt_loader()

    # Test with custom prompt
    await test_agent_with_custom_prompt()

    print("=" * 60)
    print("✅ All LLM Integration Tests Complete")
    print("=" * 60)
    print()
    print("Next Steps:")
    print("  1. Implement Google Drive API for prompt loading")
    print("  2. Store system prompts in Google Drive")
    print("  3. Integrate with agents for conversational AI")
    print()


if __name__ == "__main__":
    asyncio.run(main())
