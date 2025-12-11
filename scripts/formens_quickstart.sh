#!/bin/bash
# Formens B2B Scraping & Import - Quick Start Script

set -e  # Exit on error

echo "=========================================="
echo "FORMENS B2B - COMPLETE WORKFLOW"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if credentials are provided
if [ -z "$FORMENS_USERNAME" ] || [ -z "$FORMENS_PASSWORD" ]; then
    echo -e "${RED}❌ ERROR: Credentials not set!${NC}"
    echo ""
    echo "Please set your credentials first:"
    echo ""
    echo "  export FORMENS_USERNAME='Henning'"
    echo "  export FORMENS_PASSWORD='YourPassword'"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo -e "${GREEN}✓${NC} Credentials found"
echo "  Username: $FORMENS_USERNAME"
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}⚠️  WARNING: DATABASE_URL not set${NC}"
    echo "  Import to PostgreSQL will be skipped"
    echo "  Set it with: export DATABASE_URL='postgresql://...'"
    echo ""
    SKIP_IMPORT=1
else
    echo -e "${GREEN}✓${NC} Database URL found"
    echo ""
    SKIP_IMPORT=0
fi

# Step 1: Scraping
echo "=========================================="
echo "STEP 1: SCRAPING FABRICS"
echo "=========================================="
echo ""
echo "This will scrape ALL fabrics from b2b2.formens.ro"
echo "Expected time: 30-40 minutes for ~1988 fabrics"
echo ""
read -p "Press Enter to start scraping (or Ctrl+C to cancel)..."
echo ""

python scripts/scrape_formens_b2b.py \
  --username "$FORMENS_USERNAME" \
  --password "$FORMENS_PASSWORD" \
  --output-dir storage/fabrics

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Scraping completed successfully!${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}❌ Scraping failed!${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check your credentials"
    echo "  2. Try using a cookie instead: --cookie 'PHPSESSID=...'"
    echo "  3. See logs above for error details"
    exit 1
fi

# Check if JSON was created
if [ ! -f "storage/fabrics/formens_fabrics.json" ]; then
    echo -e "${RED}❌ JSON file not found: storage/fabrics/formens_fabrics.json${NC}"
    exit 1
fi

FABRIC_COUNT=$(python3 -c "import json; print(json.load(open('storage/fabrics/formens_fabrics.json'))['count'])" 2>/dev/null || echo "unknown")
echo -e "${GREEN}📊 Scraped $FABRIC_COUNT fabrics${NC}"
echo ""

# Step 2: Import (if DATABASE_URL is set)
if [ $SKIP_IMPORT -eq 0 ]; then
    echo "=========================================="
    echo "STEP 2: IMPORT TO POSTGRESQL"
    echo "=========================================="
    echo ""
    echo "This will import all scraped fabrics into your database"
    echo "Expected time: 2-3 minutes"
    echo ""
    read -p "Press Enter to start import (or Ctrl+C to cancel)..."
    echo ""

    python scripts/import_formens_to_db.py

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Import completed successfully!${NC}"
        echo ""
    else
        echo ""
        echo -e "${RED}❌ Import failed!${NC}"
        echo ""
        echo "Check the logs above for error details"
        exit 1
    fi

    # Step 3: Embeddings
    if [ -f "scripts/generate_fabric_embeddings.py" ]; then
        echo "=========================================="
        echo "STEP 3: GENERATE EMBEDDINGS FOR RAG"
        echo "=========================================="
        echo ""
        echo "This will generate semantic embeddings for RAG queries"
        echo "Expected time: 5-10 minutes"
        echo ""
        read -p "Press Enter to start embedding generation (or Ctrl+C to skip)..."
        echo ""

        python scripts/generate_fabric_embeddings.py

        if [ $? -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✅ Embeddings generated successfully!${NC}"
            echo ""
        else
            echo ""
            echo -e "${YELLOW}⚠️  Embedding generation had issues (check logs)${NC}"
            echo ""
        fi
    fi
else
    echo "=========================================="
    echo "STEP 2 & 3: SKIPPED (NO DATABASE_URL)"
    echo "=========================================="
    echo ""
    echo "To import to PostgreSQL, set DATABASE_URL:"
    echo "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    echo ""
    echo "Then run:"
    echo "  python scripts/import_formens_to_db.py"
    echo "  python scripts/generate_fabric_embeddings.py"
    echo ""
fi

# Summary
echo "=========================================="
echo "WORKFLOW COMPLETE! 🎉"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Scraped: $FABRIC_COUNT fabrics"
echo "  ✓ JSON: storage/fabrics/formens_fabrics.json"
echo "  ✓ Images: storage/fabrics/images/"

if [ $SKIP_IMPORT -eq 0 ]; then
    echo "  ✓ Imported to PostgreSQL"
    echo "  ✓ Embeddings generated"
    echo ""
    echo "Next steps:"
    echo "  1. Test RAG queries: 'Zeig mir Stoffe von Formens'"
    echo "  2. Verify data: python scripts/verify_embeddings.py"
else
    echo ""
    echo "Next steps:"
    echo "  1. Set DATABASE_URL to import to PostgreSQL"
    echo "  2. Run: python scripts/import_formens_to_db.py"
    echo "  3. Run: python scripts/generate_fabric_embeddings.py"
fi

echo ""
echo "For more details, see: docs/FORMENS_WORKFLOW.md"
echo ""
