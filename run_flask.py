#!/usr/bin/env python3
"""Flask Application Entry Point für LASERHENK."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Flask app
from app import app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"🚀 LASERHENK Flask Server starting...")
    print(f"   Port: {port}")
    print(f"   Debug: {debug}")
    print(f"   API Endpoints:")
    print(f"      - POST /api/auth/register")
    print(f"      - POST /api/auth/login")
    print(f"      - POST /api/auth/refresh")
    print(f"      - GET  /api/auth/me")
    print(f"      - POST /api/chat")
    print(f"      - POST /api/session")
    print(f"      - GET  /api/sessions")
    print(f"      - POST /api/crm/lead")
    print(f"      - GET  /api/crm/deals (Beta-User only)")
    print(f"      - GET  /health")
    print()

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True,
    )
