#!/usr/bin/env python3
"""
Simple wrapper to load .env and run fabric import script.
Usage: python run_import.py [--source path/to/fabrics.json]
"""
import os
import sys
import subprocess
from pathlib import Path

# Load .env file manually (without python-dotenv dependency)
env_file = Path('.env')
if env_file.exists():
    print("📂 Loading environment variables from .env...")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith('#'):
                # Handle KEY=VALUE format
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key] = value

    # Check if DATABASE_URL is set
    if 'DATABASE_URL' in os.environ:
        print("✅ DATABASE_URL loaded")
        print()
    else:
        print("❌ DATABASE_URL not found in .env!")
        sys.exit(1)
else:
    print("❌ .env file not found!")
    print("Please create .env file with DATABASE_URL")
    sys.exit(1)

# Pass all arguments to the import script
args = ['python', 'scripts/import_scraped_fabrics.py'] + sys.argv[1:]
subprocess.run(args)
