#!/usr/bin/env python3
"""
Helper script to extract Formens B2B cookie from browser for scraping.

This script helps you get the session cookie needed for scraping.

Instructions:
1. Open https://b2b2.formens.ro in your browser
2. Log in with your credentials
3. Open Developer Tools (F12)
4. Go to: Application → Cookies → https://b2b2.formens.ro
5. Find the cookie (usually PHPSESSID or similar)
6. Copy the cookie string

Then use it like this:
    python scripts/scrape_formens_b2b.py --cookie "PHPSESSID=abc123..."

Or use this script interactively:
    python scripts/get_formens_cookie.py
"""

import sys


def get_cookie_instructions():
    """Print detailed instructions for getting the cookie."""
    print("=" * 80)
    print("FORMENS B2B COOKIE EXTRACTION GUIDE")
    print("=" * 80)
    print()
    print("Follow these steps to get your session cookie:")
    print()
    print("1. Open your web browser (Chrome, Firefox, Safari, etc.)")
    print()
    print("2. Navigate to: https://b2b2.formens.ro")
    print()
    print("3. Log in with your Formens credentials")
    print()
    print("4. Open Developer Tools:")
    print("   - Chrome/Edge: F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)")
    print("   - Firefox: F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)")
    print("   - Safari: Cmd+Option+I (enable Developer menu first)")
    print()
    print("5. Go to the right tab:")
    print("   - Chrome/Edge: Application → Cookies → https://b2b2.formens.ro")
    print("   - Firefox: Storage → Cookies → https://b2b2.formens.ro")
    print("   - Safari: Storage → Cookies → b2b2.formens.ro")
    print()
    print("6. Find the session cookie (usually named 'PHPSESSID' or similar)")
    print()
    print("7. Copy the cookie value")
    print()
    print("=" * 80)
    print()


def interactive_mode():
    """Interactive mode to help user test their cookie."""
    print("INTERACTIVE COOKIE HELPER")
    print("=" * 80)
    print()
    print("Paste your cookie here (format: PHPSESSID=abc123... or just abc123...)")
    print("Press Ctrl+C to cancel")
    print()

    try:
        cookie = input("Cookie: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n\nCancelled.")
        sys.exit(0)

    if not cookie:
        print("\n❌ No cookie provided!")
        sys.exit(1)

    # Validate cookie format
    if "=" in cookie:
        name, value = cookie.split("=", 1)
        print(f"\n✅ Cookie looks valid!")
        print(f"   Name: {name}")
        print(f"   Value: {value[:20]}..." if len(value) > 20 else f"   Value: {value}")
    else:
        print(f"\n⚠️  Cookie might be incomplete (no '=' sign found)")
        print(f"   Assuming this is a PHPSESSID value")
        cookie = f"PHPSESSID={cookie}"

    print()
    print("=" * 80)
    print("USE THIS COMMAND TO START SCRAPING:")
    print("=" * 80)
    print()
    print(f'python scripts/scrape_formens_b2b.py \\')
    print(f'  --cookie "{cookie}" \\')
    print(f'  --output-dir storage/fabrics')
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Helper tool for Formens B2B cookie extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode to test cookie"
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    else:
        get_cookie_instructions()


if __name__ == "__main__":
    main()
