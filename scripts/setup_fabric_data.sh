#!/bin/bash
# ============================================================================
# LASERHENK - Fabric Data Setup Script
# ============================================================================
# Dieses Script hilft beim Einrichten der Fabric-Daten vom Scraper
# ============================================================================

set -e  # Exit on error

echo "🛠️  LASERHENK - Fabric Data Setup"
echo "===================================="
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verzeichnis-Struktur erstellen
echo "📁 Erstelle Verzeichnis-Struktur..."
mkdir -p data/fabrics/images
echo "   ✓ data/fabrics/"
echo "   ✓ data/fabrics/images/"

# Prüfen ob fabrics2.json existiert
if [ -f "data/fabrics/fabrics2.json" ]; then
    echo -e "${GREEN}✓ fabrics2.json gefunden${NC}"
    FABRIC_COUNT=$(jq 'length' data/fabrics/fabrics2.json 2>/dev/null || echo "?")
    echo "   Fabrics in JSON: $FABRIC_COUNT"
else
    echo -e "${RED}✗ fabrics2.json nicht gefunden${NC}"
    echo ""
    echo "Die Fabric-Daten müssen vom Scraper-Repository geholt werden:"
    echo ""
    echo "Option 1: Scraper-Repository klonen"
    echo "-----------------------------------------"
    echo "cd /tmp"
    echo "git clone https://github.com/Henninglutz/henk.bettercallhenk.de.git"
    echo "cp henk.bettercallhenk.de/output/fabrics2.json $(pwd)/data/fabrics/"
    echo ""
    echo "Option 2: Daten von bestehendem Clone kopieren"
    echo "-----------------------------------------------"
    echo "Falls das Scraper-Repository bereits existiert:"
    echo "cp /pfad/zum/scraper/output/fabrics2.json $(pwd)/data/fabrics/"
    echo ""
    echo "Option 3: Daten manuell vom Server holen"
    echo "-----------------------------------------"
    echo "scp user@server:/pfad/zu/fabrics2.json $(pwd)/data/fabrics/"
    echo ""
fi

# Prüfen ob Images existieren
IMAGE_COUNT=$(find data/fabrics/images -type f 2>/dev/null | wc -l)
if [ "$IMAGE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ $IMAGE_COUNT Bilder gefunden${NC}"
else
    echo -e "${RED}✗ Keine Bilder in data/fabrics/images/${NC}"
    echo ""
    echo "Die Fabric-Bilder müssen vom Scraper geholt werden:"
    echo ""
    echo "Option 1: Vom Scraper-Repository"
    echo "-----------------------------------------"
    echo "cp -r henk.bettercallhenk.de/output/images/* $(pwd)/data/fabrics/images/"
    echo ""
    echo "Option 2: Manuell vom Server"
    echo "-----------------------------------------"
    echo "rsync -avz user@server:/pfad/zu/images/ $(pwd)/data/fabrics/images/"
    echo ""
fi

echo ""
echo "📊 Status"
echo "========="
if [ -f "data/fabrics/fabrics2.json" ] && [ "$IMAGE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Alle Daten vorhanden - bereit für Import!${NC}"
    echo ""
    echo "Nächster Schritt:"
    echo "  python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json"
else
    echo -e "${YELLOW}⚠ Daten fehlen noch${NC}"
    echo ""
    echo "Sobald die Daten vorhanden sind:"
    echo "  1. Fabric-Daten importieren:"
    echo "     python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json"
    echo ""
    echo "  2. Embeddings generieren:"
    echo "     python scripts/generate_fabric_embeddings.py"
fi

echo ""
echo "🔗 Scraper Repository:"
echo "   https://github.com/Henninglutz/henk.bettercallhenk.de"
echo ""
