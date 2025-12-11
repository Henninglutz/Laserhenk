#!/bin/bash
# Wrapper script to load .env and run fabric import

set -e

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with DATABASE_URL"
    exit 1
fi

# Load .env and export variables
echo "📂 Loading environment variables from .env..."
export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not found in .env!"
    exit 1
fi

echo "✅ DATABASE_URL loaded"
echo ""

# Run the import script
python scripts/import_scraped_fabrics.py "$@"
