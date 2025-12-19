#!/usr/bin/env python3
"""
CRM Integration Test Script

Tests:
1. CRMTool with/without API key
2. Person creation and duplicate detection
3. Deal creation
4. MOCK lead fallback
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

from tools.crm_tool import CRMTool, PipedriveClient
from models.tools import CRMLeadCreate


def test_pipedrive_configuration():
    """Test 1: Check Pipedrive configuration."""
    print("\n" + "="*60)
    print("TEST 1: Pipedrive Configuration")
    print("="*60)

    api_key = os.getenv('PIPEDRIVE_API_KEY')
    domain = os.getenv('PIPEDRIVE_DOMAIN', 'api.pipedrive.com')

    print(f"PIPEDRIVE_API_KEY: {'✅ SET' if api_key else '❌ NOT SET'}")
    print(f"PIPEDRIVE_DOMAIN: {domain}")

    if api_key:
        print(f"API Key (masked): {api_key[:10]}...{api_key[-4:]}")
    else:
        print("⚠️  WARNING: Pipedrive not configured - MOCK leads will be created")

    return bool(api_key)


async def test_crm_tool_initialization():
    """Test 2: CRMTool initialization."""
    print("\n" + "="*60)
    print("TEST 2: CRMTool Initialization")
    print("="*60)

    crm_tool = CRMTool()

    print(f"CRMTool instance: {crm_tool}")
    print(f"API Key configured: {'✅' if crm_tool.api_key else '❌'}")
    print(f"Client instance: {'✅' if crm_tool.client else '❌'}")

    return crm_tool


async def test_lead_creation_without_api():
    """Test 3: Lead creation WITHOUT API key (MOCK)."""
    print("\n" + "="*60)
    print("TEST 3: Lead Creation (MOCK Mode)")
    print("="*60)

    # Temporarily remove API key from environment
    original_api_key = os.environ.pop('PIPEDRIVE_API_KEY', None)

    try:
        # Force no API key by removing from env
        crm_tool = CRMTool()

        lead_data = CRMLeadCreate(
            customer_name="Test User (MOCK)",
            email="test-mock@example.com",
            phone="+49 123 456789",
            notes="Test lead - MOCK mode",
            deal_value=1500.0,
        )

        print(f"Creating lead: {lead_data.customer_name}")
        response = await crm_tool.create_lead(lead_data)

        print(f"Success: {response.success}")
        print(f"Lead ID: {response.lead_id}")
        print(f"Message: {response.message}")

        assert response.lead_id == "no_api_key", f"Expected 'no_api_key', got '{response.lead_id}'"
        assert not response.success, "Expected success=False"

        print("✅ MOCK lead creation works correctly")

    finally:
        # Restore original API key
        if original_api_key:
            os.environ['PIPEDRIVE_API_KEY'] = original_api_key


async def test_lead_creation_with_api(crm_tool: CRMTool):
    """Test 4: Lead creation WITH API key."""
    print("\n" + "="*60)
    print("TEST 4: Lead Creation (Real Pipedrive)")
    print("="*60)

    if not crm_tool.client:
        print("⏭️  SKIPPED: No API key configured")
        return

    lead_data = CRMLeadCreate(
        customer_name="Test User (Real)",
        email=f"test-real-{os.urandom(4).hex()}@example.com",  # Unique email
        phone="+49 123 456789",
        notes="Test lead - Real API call",
        deal_value=2000.0,
    )

    print(f"Creating lead: {lead_data.customer_name}")
    print(f"Email: {lead_data.email}")

    try:
        response = await crm_tool.create_lead(lead_data)

        print(f"Success: {response.success}")
        print(f"Lead ID: {response.lead_id}")
        print(f"Deal ID: {response.deal_id}")
        print(f"Message: {response.message}")

        if response.success:
            print("✅ Real lead created in Pipedrive!")
            print(f"   Person ID: {response.lead_id}")
            if response.deal_id:
                print(f"   Deal ID: {response.deal_id}")
        else:
            print(f"❌ Lead creation failed: {response.message}")

    except Exception as e:
        print(f"❌ ERROR: {e}")


async def test_duplicate_detection(crm_tool: CRMTool):
    """Test 5: Duplicate email detection."""
    print("\n" + "="*60)
    print("TEST 5: Duplicate Detection")
    print("="*60)

    if not crm_tool.client:
        print("⏭️  SKIPPED: No API key configured")
        return

    test_email = f"duplicate-test-{os.urandom(4).hex()}@example.com"

    # Create first lead
    lead_data_1 = CRMLeadCreate(
        customer_name="Duplicate Test 1",
        email=test_email,
        phone="+49 111 111111",
        deal_value=1000.0,
    )

    print(f"Creating first lead with email: {test_email}")
    response_1 = await crm_tool.create_lead(lead_data_1)
    print(f"First lead ID: {response_1.lead_id}")

    # Create duplicate
    lead_data_2 = CRMLeadCreate(
        customer_name="Duplicate Test 2",
        email=test_email,  # Same email!
        phone="+49 222 222222",
        deal_value=2000.0,
    )

    print(f"\nCreating duplicate with same email: {test_email}")
    response_2 = await crm_tool.create_lead(lead_data_2)
    print(f"Second lead ID: {response_2.lead_id}")

    if response_1.lead_id == response_2.lead_id:
        print("✅ Duplicate detection works! Same person used.")
    else:
        print("⚠️  Different person IDs - duplicate detection may not work")


async def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("# CRM Integration Test Suite")
    print("#"*60)

    # Test 1: Configuration
    has_api_key = test_pipedrive_configuration()

    # Test 2: Initialization
    crm_tool = await test_crm_tool_initialization()

    # Test 3: MOCK lead
    await test_lead_creation_without_api()

    # Test 4: Real lead (if API key configured)
    if has_api_key:
        await test_lead_creation_with_api(crm_tool)
        await test_duplicate_detection(crm_tool)
    else:
        print("\n" + "="*60)
        print("⚠️  Real Pipedrive tests skipped (no API key)")
        print("   To test with real API:")
        print("   1. Add PIPEDRIVE_API_KEY to .env")
        print("   2. Run script again")
        print("="*60)

    print("\n" + "#"*60)
    print("# Test Suite Complete")
    print("#"*60)


if __name__ == "__main__":
    asyncio.run(main())
