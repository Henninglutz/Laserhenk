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

### 3. `scrape_formens_b2b.py`

**Zweck:** Lädt den kompletten Stoffkatalog (≈1988 Artikel) von b2b2.formens.ro erneut herunter, inklusive fehlender Details wie Preis-Kategorie, Zusammensetzung, Ursprung und Bilder.

**Was es macht:**
- Meldet sich mit E-Mail/Passwort oder einem bestehenden Session-Cookie am B2B-Portal an
- Durchläuft die paginierten Stofflisten und sammelt alle Detail-Links
- Extrahiert Attribute aus JSON-LD, Tabellen und Definition Lists (inkl. Preis-Kat., Composition, Origin, Gewicht)
- Lädt das Hauptbild jedes Stoffs herunter (für DALL·E/Moodboards)
- Schreibt die Ergebnisse nach `storage/fabrics/formens_fabrics.json` und speichert Bilder unter `storage/fabrics/images/`

**Usage:**
```bash
python scripts/scrape_formens_b2b.py \
  --email "$FORMENS_EMAIL" --password "$FORMENS_PASSWORD" \
  --output-dir storage/fabrics --max-pages 120

# Alternativ: Browser-Cookie statt Login nutzen
python scripts/scrape_formens_b2b.py --cookie "sessionid=..." --max-pages 120
```

**Output:**
- `storage/fabrics/formens_fabrics.json` mit allen Stoffen und Metadaten
- Bilder im Ordner `storage/fabrics/images/`

**Dauer:** Hängt von der Portal-Latenz ab; Skript pausiert standardmäßig ~0.7s zwischen Requests, um Throttling zu vermeiden

**Hinweise:**
- `--listing-path` und `--page-param` sind konfigurierbar, falls die Pagination angepasst werden muss
- `--no-images` kann genutzt werden, wenn nur Metadaten benötigt werden

---

### 3b. `import_formens_scrape_to_rag.py`

**Zweck:** Schreibt die von `scrape_formens_b2b.py` erzeugten Stoffdaten in die Postgres-Datenbank (Tabelle `fabrics`) und erzeugt optional RAG-Dokumente mit Embeddings für die `rag_docs`-Tabelle.

**Anmeldung / Zugangsdaten:**
- Datenbank: `POSTGRES_CONNECTION_STRING` **oder** `DATABASE_URL` in `.env`
- OpenAI (nur für RAG-Embeddings): `OPENAI_API_KEY` in `.env`
- Scraper-Login (Formens): `FORMENS_EMAIL`, `FORMENS_PASSWORD` oder `--cookie` beim Scraper-Aufruf

**Usage:**
```bash
# Nur Datenbank-Update (kein RAG, keine Embeddings nötig)
python scripts/import_formens_scrape_to_rag.py \
  --input storage/fabrics/formens_fabrics.json \
  --no-rag

# Mit RAG-Embeddings (Standard-Kategorie: fabrics_formens)
python scripts/import_formens_scrape_to_rag.py \
  --input storage/fabrics/formens_fabrics.json \
  --rag-category fabrics_formens \
  --batch-size 15
```

**Was passiert:**
- Upsert in `fabrics` anhand `fabric_code` (Code, Name, Zusammensetzung, Gewicht, Preis-Kategorie, Ursprung in `additional_metadata`)
- Optional: Erstellung eines RAG-Text-Chunks pro Stoff + OpenAI-Embedding → Insert/Update in `rag_docs`
- Idempotent: Wiederholtes Ausführen aktualisiert bestehende Datensätze

**Dauer & Kosten:**
- Ohne RAG: Sekundenbereich
- Mit RAG: abhängig von OpenAI-Rate-Limit; Kosten nur für Embeddings

**Hinweis:** Nach erfolgreichem Import sind RAG-Abfragen wie „zeig mir Stoffe“ direkt nutzbar. Bei Bedarf kann `--rag-category` angepasst werden, um die Dokumente zu isolieren.

---

## 🔄 Wie geht es nach dem Scrape weiter?

1. **Scraper laufen lassen** (Session-Cookie oder Login nutzen), damit `storage/fabrics/formens_fabrics.json` und Bilder befüllt sind.
2. **Importer starten**, um Postgres und optional RAG zu aktualisieren:

   ```bash
   # Nur DB aktualisieren
   python scripts/import_formens_scrape_to_rag.py --input storage/fabrics/formens_fabrics.json --no-rag

   # DB + RAG (Embeddings anlegen)
   python scripts/import_formens_scrape_to_rag.py \
     --input storage/fabrics/formens_fabrics.json \
     --rag-category fabrics_formens \
     --batch-size 25
   ```

3. **Kontroll-Queries in Postgres**, um den Erfolg zu prüfen:

   ```sql
   -- Anzahl Stoffe
   SELECT COUNT(*) FROM fabrics;

   -- Price Category & Composition sollten im JSON-Feld liegen
   SELECT fabric_code, additional_metadata
   FROM fabrics
   WHERE additional_metadata ? 'price_category'
   ORDER BY fabric_code
   LIMIT 5;

   -- Falls RAG aktiv: Anzahl Embeddings prüfen
   SELECT COUNT(*) FROM rag_docs WHERE category = 'fabrics_formens';
   ```

4. **Erneute Läufe** sind idempotent (Upsert). Bei neuen Stoffen einfach Scraper + Importer erneut starten.

---

## 🚀 Setup-Reihenfolge

Nach frischem Database Setup:

```bash
# 1. Pricing Schema erstellen
psql -U henk_user -d henk_rag -f scripts/create_pricing_schema.sql

# 2. Dependencies installieren
pip install -r requirements.txt

# 3. Formens-Stoffe neu ziehen
python scripts/scrape_formens_b2b.py --email "$FORMENS_EMAIL" --password "$FORMENS_PASSWORD"

# 4. Postgres (und optional RAG) updaten
python scripts/import_formens_scrape_to_rag.py --input storage/fabrics/formens_fabrics.json --rag-category fabrics_formens

# 5. Verify (optional)
python verify_embeddings.py
```

---

## 📊 Erwartete Datenbank-State nach Scripts

| Tabelle | Vor Scripts | Nach Scripts |
|---------|-------------|--------------|
| `fabrics` | 0 Zeilen | 1988 Zeilen (nach Scrape + Import) |
| `fabric_embeddings` | 0 Zeilen | ~7952 Zeilen (optional, falls Script `generate_fabric_embeddings.py` genutzt wird) |
| `pricing_rules` | Nicht vorhanden | 63 Zeilen |
| `pricing_extras` | Nicht vorhanden | 9 Zeilen |
| `rag_docs` | 0 Zeilen | 1994 Zeilen (optional, falls `import_formens_scrape_to_rag.py` mit RAG läuft) |

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
