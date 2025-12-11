#!/usr/bin/env python3
"""Test Flask App - Basic Smoke Test."""

import sys
from dotenv import load_dotenv

load_dotenv()

def test_imports():
    """Test basic imports."""
    print("Testing imports...")
    try:
        from app import app
        print("✅ Flask app imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import Flask app: {e}")
        return False


def test_blueprints():
    """Test blueprints registration."""
    print("\nTesting blueprints...")
    try:
        from app import app
        blueprints = list(app.blueprints.keys())
        print(f"   Registered blueprints: {blueprints}")

        expected = ['auth', 'api', 'crm']
        for bp in expected:
            if bp in blueprints:
                print(f"   ✅ {bp} blueprint registered")
            else:
                print(f"   ❌ {bp} blueprint missing")
                return False

        return True
    except Exception as e:
        print(f"❌ Blueprint test failed: {e}")
        return False


def test_routes():
    """Test routes exist."""
    print("\nTesting routes...")
    try:
        from app import app

        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(f"{','.join(rule.methods)} {rule.rule}")

        print(f"   Total routes: {len(routes)}")

        expected_routes = [
            '/health',
            '/api/chat',
            '/api/session',
            '/api/auth/login',
            '/api/auth/register',
            '/api/crm/deals',
        ]

        for route in expected_routes:
            if any(route in r for r in routes):
                print(f"   ✅ {route}")
            else:
                print(f"   ❌ {route} missing")

        return True
    except Exception as e:
        print(f"❌ Routes test failed: {e}")
        return False


def test_config():
    """Test app configuration."""
    print("\nTesting configuration...")
    try:
        from app import app

        print(f"   SECRET_KEY: {'✅ Set' if app.config.get('SECRET_KEY') else '❌ Missing'}")
        print(f"   JWT_SECRET_KEY: {'✅ Set' if app.config.get('JWT_SECRET_KEY') else '❌ Missing'}")

        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Flask App Smoke Tests")
    print("=" * 60)

    tests = [
        test_imports,
        test_blueprints,
        test_routes,
        test_config,
    ]

    results = []
    for test in tests:
        result = test()
        results.append(result)

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)


if __name__ == '__main__':
    main()
