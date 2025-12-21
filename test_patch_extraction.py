#!/usr/bin/env python3
"""Test script for PatchDecision extraction with Pydantic-AI / Structured Outputs."""

import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.design_patch_agent import DesignPatchAgent


async def test_patch_extraction():
    """Test PatchDecision extraction with various user feedback examples."""

    print("=" * 80)
    print("HENK Design Patch Extraction - Test Suite")
    print("=" * 80)
    print()

    # Initialize agent
    agent = DesignPatchAgent()
    print(f"✅ Agent initialized")
    print()

    # Test cases
    test_cases = [
        {
            "name": "Einreiher mit fallendem Revers",
            "feedback": "bitte nochmal als Einreiher und mit fallendem Revers",
            "expected": {
                "jacket_front": "single_breasted",
                "lapel_roll": "rolling",
            }
        },
        {
            "name": "Ohne Weste",
            "feedback": "Nochmal ohne Weste bitte",
            "expected": {
                "wants_vest": False,
            }
        },
        {
            "name": "Italienischer Stil ohne Polster",
            "feedback": "modern, leicht, italienisch, ohne Futter ohne Polster, mit aufgesetzten Taschen",
            "expected": {
                "shoulder_padding": "none",
            }
        },
        {
            "name": "Spitzrevers mit Bundfalte",
            "feedback": "fallendes Revers, ohne Schulterpolster und mit Bundfalte",
            "expected": {
                "lapel_roll": "rolling",
                "shoulder_padding": "none",
                "trouser_front": "pleats",
            }
        },
        {
            "name": "Zweireihig mit Weste",
            "feedback": "ich hätte gerne einen Zweireiter mit Weste und Spitzrevers",
            "expected": {
                "jacket_front": "double_breasted",
                "wants_vest": True,
                "lapel_style": "peak",
            }
        },
    ]

    # Run tests
    for i, test_case in enumerate(test_cases, 1):
        print(f"TEST {i}/{len(test_cases)}: {test_case['name']}")
        print(f"Input: '{test_case['feedback']}'")
        print()

        try:
            decision = await agent.extract_patch_decision(test_case['feedback'])

            print(f"✅ Extraction successful!")
            print(f"   Confidence: {decision.confidence:.2f}")
            print(f"   Changed Fields: {decision.changed_fields}")
            print()
            print(f"Patch Details:")

            # Display extracted patch
            patch_dict = decision.patch.model_dump(exclude_none=True)
            if patch_dict:
                for field, value in patch_dict.items():
                    print(f"   • {field}: {value}")
            else:
                print("   (no changes detected)")

            # Check expected fields
            expected = test_case['expected']
            all_correct = True
            for field, expected_value in expected.items():
                actual_value = getattr(decision.patch, field, None)
                if actual_value == expected_value:
                    print(f"   ✓ {field} matches expected: {expected_value}")
                else:
                    print(f"   ✗ {field} mismatch: expected {expected_value}, got {actual_value}")
                    all_correct = False

            if all_correct:
                print(f"   🎉 All expected fields matched!")

        except Exception as exc:
            print(f"❌ Extraction failed: {exc}")

        print()
        print("-" * 80)
        print()

    print("=" * 80)
    print("Test Suite Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_patch_extraction())
