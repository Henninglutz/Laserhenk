# 🛠️ Laserhenk Scripts

Utility scripts für Datenbank-Setup und Maintenance.

---

## 📋 Verfügbare Scripts

### 1. `create_pricing_schema.sql`

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

### 2. `generate_fabric_embeddings.py`

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
# 1. Pricing Schema erstellen
psql -U henk_user -d henk_rag -f scripts/create_pricing_schema.sql

# 2. Dependencies installieren
pip install sqlalchemy asyncpg openai python-dotenv

# 3. Fabric Embeddings generieren
python scripts/generate_fabric_embeddings.py

# 4. Verify (optional)
python verify_embeddings.py
```

---

## 📊 Erwartete Datenbank-State nach Scripts

| Tabelle | Vor Scripts | Nach Scripts |
|---------|-------------|--------------|
| `fabrics` | 1988 Zeilen | 1988 Zeilen |
| `fabric_embeddings` | 0 Zeilen | ~7952 Zeilen |
| `pricing_rules` | Nicht vorhanden | 63 Zeilen |
| `pricing_extras` | Nicht vorhanden | 9 Zeilen |
| `rag_docs` | 483 Zeilen | 483 Zeilen |

---

## 🐛 Troubleshooting

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
