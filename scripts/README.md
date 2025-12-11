# 🛠️ Laserhenk Scripts

Utility scripts für Datenbank-Setup und Maintenance.

---

## 📋 Verfügbare Scripts

### 1. `import_scraped_fabrics.py` ⭐ NEW

**Zweck:** Importiert 2256+ Stoffe von henk.bettercallhenk.de Scraper

**Was es macht:**
- Liest Fabric-Daten aus `data/fabrics/fabrics2.json`
- Parsed Weight-Strings ("250g/m²" → 250) zu Integer
- Updated existierende Fabrics (by fabric_code) oder fügt neue ein
- Speichert Original-Weight in `additional_metadata`
- Batch-Processing mit Progress-Tracking

**Prerequisites:**
- `.env` mit `DATABASE_URL` oder `POSTGRES_CONNECTION_STRING`
- Scraped Fabric JSON: `data/fabrics/fabrics2.json`
- Dependencies: `asyncpg`, `python-dotenv`

**Usage:**
```bash
# Default: storage/fabrics2.json
python scripts/import_scraped_fabrics.py

# Custom source path
python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json
```

**Output:**
```
✓ Updated: X existing fabrics
✓ Inserted: Y new fabrics
Total fabrics: 2256
With metadata: 2256 (100.0%)
```

**Dauer:** 2-5 Minuten (abhängig von Datenmenge)

---

### 2. `import_fabric_catalog.py`

**Zweck:** Importiert 140 Fabrics aus MTM Cards PDF Catalog

**Was es macht:**
- Liest `drive_mirror/henk/fabrics/fabric_catalog.json`
- Extracted Metadata (Supplier, Composition, Weight) aus Context
- Updated existierende Fabrics oder fügt neue ein
- Behält Tier und Reference Information

**Usage:**
```bash
python scripts/import_fabric_catalog.py
```

**Output:**
```
✓ Inserted: ~140 new fabrics
✓ Updated: 0 existing fabrics
```

---

### 3. `update_fabric_metadata.py`

**Zweck:** Updated fehlende Fabric-Daten aus CSV

**Was es macht:**
- Checked Data Completeness (Name, Composition, Color, Pattern, Weight)
- Generiert Sample CSV Template
- Updated Fabrics aus CSV-Daten

**Usage:**
```bash
# Check completeness
python scripts/update_fabric_metadata.py --check

# Generate template
python scripts/update_fabric_metadata.py --generate-template fabrics_data.csv

# Update from CSV
python scripts/update_fabric_metadata.py --source fabrics_data.csv
```

---

### 4. `check_fabric_data_completeness.sql`

**Zweck:** SQL Queries zur Data Completeness Prüfung

**Was es macht:**
- Total Count und Field Completeness
- Embeddings Linkage Check
- Sample von incomplete Fabrics
- Embedding Content Preview

**Usage:**
```bash
psql -U henk_user -d henk_rag -f scripts/check_fabric_data_completeness.sql
```

---

### 5. `create_pricing_schema.sql`

**Zweck:** Erstellt das Pricing-Schema in der Datenbank

**Was es macht:**
- Erstellt `pricing_rules` Tabelle
- Erstellt `pricing_extras` Tabelle
- Fügt initiale Pricing-Daten ein (Preiskategorien 1-9)
- Erstellt Helper Views für einfache Queries

**Usage:**
```bash
psql -U henk_user -d henk_rag -f scripts/create_pricing_schema.sql
```

**Output:**
- Tabellen erstellt
- 63 Pricing Rules eingefügt (9 Kategorien × 7 Garment Types)
- 9 Pricing Extras eingefügt
- 2 Views erstellt

**Dauer:** < 1 Sekunde

---

### 6. `generate_fabric_embeddings.py`

**Zweck:** Generiert Embeddings für alle Stoffe in der Datenbank

**Was es macht:**
- Liest alle 1988 Stoffe aus `fabrics` Tabelle
- Erstellt 4 Content-Chunks pro Stoff:
  1. **Characteristics** (Composition, Weight, Color, Pattern)
  2. **Visual** (Visual attributes, properties)
  3. **Usage** (Category, Season, Occasion)
  4. **Technical** (Care, Origin, Supplier)
- Generiert Embeddings mit OpenAI `text-embedding-3-small`
- Speichert in `fabric_embeddings` Tabelle

**Prerequisites:**
- `.env` mit `OPENAI_API_KEY` und `POSTGRES_CONNECTION_STRING`
- OpenAI API Credits
- Dependencies: `sqlalchemy`, `asyncpg`, `openai`, `python-dotenv`

**Usage:**
```bash
# Normal execution
python scripts/generate_fabric_embeddings.py

# Dry run (test without inserting)
python scripts/generate_fabric_embeddings.py --dry-run

# Custom batch size
python scripts/generate_fabric_embeddings.py --batch-size 100
```

**Output:**
```
Fabrics Processed: 1988
Chunks Created: ~7952
Embeddings Generated: ~7952
Total Tokens Used: ~400,000
Estimated Cost: ~$0.008
```

**Dauer:** 15-30 Minuten (abhängig von OpenAI API Rate Limits)

**Kosten:** ~$0.01 (vernachlässigbar)

---

## 🚀 Setup-Reihenfolge

Nach frischem Database Setup:

```bash
# 0. Dependencies installieren
pip install sqlalchemy asyncpg openai python-dotenv

# 1. Fabric-Daten importieren (WICHTIG: Vor Embeddings!)
python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json

# 2. Optional: MTM Catalog importieren (140 weitere Fabrics)
python scripts/import_fabric_catalog.py

# 3. Data Completeness prüfen
python scripts/update_fabric_metadata.py --check

# 4. Pricing Schema erstellen
psql -U henk_user -d henk_rag -f scripts/create_pricing_schema.sql

# 5. Fabric Embeddings generieren
python scripts/generate_fabric_embeddings.py

# 6. Verify (optional)
python scripts/verify_embeddings.py
```

---

## 📊 Erwartete Datenbank-State nach Scripts

| Tabelle | Vor Scripts | Nach Import | Nach Embeddings |
|---------|-------------|-------------|-----------------|
| `fabrics` | 1988 (ohne Metadata) | 2256 (mit Metadata) | 2256 |
| `fabric_embeddings` | 43M (alt) | 43M (alt) | ~9024 (neu) |
| `pricing_rules` | Nicht vorhanden | 63 Zeilen | 63 Zeilen |
| `pricing_extras` | Nicht vorhanden | 9 Zeilen | 9 Zeilen |
| `rag_docs` | 483 Zeilen | 483 Zeilen | 483 Zeilen |

**Wichtig:** Nach Fabric-Import müssen die Embeddings neu generiert werden!

---

## 🐛 Troubleshooting

### Error: "fabrics2.json not found"
- Checke ob Scraper-Daten vorhanden: `data/fabrics/fabrics2.json`
- Alternativ-Location: `storage/fabrics2.json`
- Falls nicht vorhanden: Run henk.bettercallhenk.de Scraper

### Error: "invalid input for query argument: '250g/m²'"
- ✅ **FIXED** in latest version von `import_scraped_fabrics.py`
- Weight-Parsing konvertiert jetzt automatisch "250g/m²" → 250
- Falls Error weiterhin auftritt: Git pull und Script erneut ausführen

### Error: "Fabrics have NULL composition/color/pattern"
- Run `import_scraped_fabrics.py` to fill in missing metadata
- Checke mit: `python scripts/update_fabric_metadata.py --check`
- Falls Daten immer noch fehlen: Scraper erneut ausführen

### Error: "No module named 'openai'"
```bash
pip install openai
```

### Error: "OPENAI_API_KEY not set"
- Checke `.env` Datei
- Stelle sicher, dass `.env` im Root-Verzeichnis liegt

### Error: "POSTGRES_CONNECTION_STRING not set"
- Checke `.env` Datei
- Format: `postgresql://user:password@localhost:5432/henk_rag`

### OpenAI Rate Limit Error
- Reduziere `--batch-size` (default: 50)
- Warte 60 Sekunden und führe Script erneut aus
- Script ist idempotent (kann mehrfach ausgeführt werden)

### Database Connection Timeout
- Checke, ob PostgreSQL läuft: `systemctl status postgresql`
- Checke Connection String in `.env`

---

## 🔍 Verification Queries

Nach Ausführung der Scripts:

```sql
-- Check pricing rules
SELECT price_category, garment_type, base_price
FROM pricing_rules
ORDER BY CAST(price_category AS INTEGER), garment_type;

-- Check fabric embeddings
SELECT
    COUNT(*) as total_embeddings,
    chunk_type,
    COUNT(DISTINCT fabric_id) as unique_fabrics
FROM fabric_embeddings
GROUP BY chunk_type;

-- Check embeddings dimensions
SELECT vector_dims(embedding) as dimensions
FROM fabric_embeddings
LIMIT 1;

-- Expected output: 384
```

---

## 📚 Related Documentation

- `docs/DATABASE_ANALYSIS.md` - Vollständige Datenbank-Analyse
- `docs/RAG_SETUP.md` - RAG Setup Guide
- `verify_embeddings.py` - Embedding Dimensions Verification

---

**Status:** ✅ Scripts ready for execution
