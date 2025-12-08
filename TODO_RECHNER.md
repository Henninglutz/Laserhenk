# 💻 TODO RECHNER - Am PC
**Datum**: 2025-12-08
**Für**: Technische Implementierung, Code, Secrets

---

## 🔐 SCHRITT 1: Environment Secrets einrichten

### 1.1 `.env` Datei erstellen

```bash
# Im Projekt-Root
cp .env.example .env
nano .env  # oder vim/code .env
```

### 1.2 Secrets ausfüllen (aus Smartphone-Notizen)

```bash
# ============================================================================
# OpenAI / LLM Configuration
# ============================================================================
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # ← DEIN KEY
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_ORG_ID=org-xxxxxxxxxxxxxxxx  # ← OPTIONAL

# ============================================================================
# PostgreSQL RAG Database
# ============================================================================
# Lokal:
DATABASE_URL=postgresql://user:password@localhost:5432/henk_rag
POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/henk_rag

# Remote (falls Hosting):
# DATABASE_URL=postgresql://user:password@hostname:5432/henk_rag

DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30

# ============================================================================
# Vector Embeddings
# ============================================================================
EMBEDDING_DIMENSION=384
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ============================================================================
# PIPEDRIVE CRM Integration
# ============================================================================
PIPEDRIVE_API_KEY=your_pipedrive_key_here  # ← DEIN KEY
PIPEDRIVE_DOMAIN=henninglutz-company  # ← DEINE DOMAIN
PIPEDRIVE_API_URL=https://api.pipedrive.com/v1

# ============================================================================
# Google Drive Integration
# ============================================================================
GOOGLE_DRIVE_CREDENTIALS_PATH=./credentials/google_drive_credentials.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here  # ← DEINE FOLDER ID

# ============================================================================
# SAIA 3D Measurement (später)
# ============================================================================
SAIA_API_KEY=your_saia_key_here
SAIA_API_URL=https://api.saia.com
SAIA_TIMEOUT=30

# ============================================================================
# Application Settings
# ============================================================================
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=true

# ============================================================================
# Security
# ============================================================================
# Generiere mit: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=GENERIERE_RANDOM_32_CHARS_HIER
JWT_SECRET=GENERIERE_RANDOM_32_CHARS_HIER
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# ============================================================================
# Feature Flags
# ============================================================================
ENABLE_DALLE=true
ENABLE_SAIA=false
ENABLE_CRM=true
ENABLE_RAG=true
```

### 1.3 Secrets generieren

```bash
# Secret Keys generieren
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"

# In .env kopieren
```

**✅ Checkpoint:** `.env` Datei komplett ausgefüllt

---

## 🗄️ SCHRITT 2: Datenbank Setup

### 2.1 PostgreSQL prüfen

```bash
# Ist PostgreSQL installiert?
psql --version

# Läuft PostgreSQL?
sudo systemctl status postgresql

# Falls nicht:
sudo systemctl start postgresql
```

### 2.2 Datenbank erstellen

```bash
# Als postgres User
sudo -u postgres psql

# In psql:
CREATE DATABASE henk_rag;
CREATE USER henk_user WITH PASSWORD 'dein_sicheres_passwort';
GRANT ALL PRIVILEGES ON DATABASE henk_rag TO henk_user;

# pgvector Extension aktivieren
\c henk_rag
CREATE EXTENSION IF NOT EXISTS vector;

# Prüfen
\dx  # Zeigt alle Extensions

# Exit
\q
```

### 2.3 Datenbank-Schema anlegen

```bash
# Falls Schema-Datei vorhanden:
psql -U henk_user -d henk_rag -f database/schema.sql

# Oder manuell Tabellen erstellen (siehe unten)
```

**Minimale Tabellen für Start:**

```sql
-- Fabrics Tabelle
CREATE TABLE IF NOT EXISTS fabrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fabric_code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255),
    supplier VARCHAR(255),
    composition TEXT,
    weight INTEGER,
    color VARCHAR(100),
    pattern VARCHAR(100),
    category VARCHAR(100),
    stock_status VARCHAR(50),
    origin VARCHAR(100),
    care_instructions TEXT,
    additional_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Fabric Embeddings Tabelle
CREATE TABLE IF NOT EXISTS fabric_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fabric_id UUID REFERENCES fabrics(id) ON DELETE CASCADE,
    chunk_id VARCHAR(255) UNIQUE NOT NULL,
    chunk_type VARCHAR(50),
    content TEXT NOT NULL,
    embedding vector(384),
    embedding_metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indizes für Performance
CREATE INDEX IF NOT EXISTS idx_fabric_code ON fabrics(fabric_code);
CREATE INDEX IF NOT EXISTS idx_fabric_category ON fabrics(category);
CREATE INDEX IF NOT EXISTS idx_embedding_fabric ON fabric_embeddings(fabric_id);
CREATE INDEX IF NOT EXISTS idx_embedding_chunk ON fabric_embeddings(chunk_id);
```

### 2.4 Datenbank-Verbindung testen

```bash
# Mit Script testen
python scripts/inspect_db.py

# Erwartete Ausgabe:
# ✅ Verbindung erfolgreich
# 📊 Tabellen gefunden: fabrics, fabric_embeddings
# 📈 Anzahl Stoffe: 0 (oder mehr falls schon importiert)
```

**✅ Checkpoint:** Datenbank läuft und ist erreichbar

---

## 📥 SCHRITT 3: Fabrics in Datenbank importieren

### 3.1 Fabric-Katalog prüfen

```bash
# Wie viele Stoffe sind im JSON?
jq '.fabrics | length' drive_mirror/henk/fabrics/fabric_catalog.json

# Erste 3 Stoffe anzeigen
jq '.fabrics[0:3] | .[] | {reference, cat_raw, supplier}' drive_mirror/henk/fabrics/fabric_catalog.json
```

### 3.2 Import-Script erstellen (NEUE DATEI)

```bash
# Erstelle neues Script
nano scripts/import_fabrics_to_db.py
```

**Inhalt:**

```python
"""Import fabric_catalog.json to PostgreSQL Database"""

import asyncio
import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")

async def import_fabrics():
    """Import all fabrics from JSON to database."""

    # Load JSON
    with open('drive_mirror/henk/fabrics/fabric_catalog.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    fabrics = data.get('fabrics', [])
    print(f"📦 Found {len(fabrics)} fabrics in JSON")

    # Connect to DB
    connection_string = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(connection_string, echo=False)

    async with engine.begin() as conn:
        inserted = 0
        skipped = 0

        for fabric in fabrics:
            try:
                # Extract data
                fabric_code = fabric.get('reference', '')
                name = fabric.get('context', '')[:255] if fabric.get('context') else None
                supplier = name.split('/')[1].strip() if '/' in name else None
                composition = None

                # Parse context for composition
                context = fabric.get('context', '')
                if 'Virgin Wool' in context:
                    composition = context.split(',')[0] if ',' in context else None

                # Weight
                weight = None
                if 'gr/ml' in context:
                    try:
                        weight = int(context.split('gr/ml')[0].split()[-1])
                    except:
                        pass

                # CAT and Tier
                cat_raw = fabric.get('cat_raw', '')
                category = cat_raw

                # Additional metadata
                additional_metadata = {
                    'page': fabric.get('page'),
                    'price_tiers': fabric.get('price_tiers', {})
                }

                # Insert
                query = text("""
                    INSERT INTO fabrics (
                        fabric_code, name, supplier, composition, weight,
                        category, additional_metadata
                    ) VALUES (
                        :fabric_code, :name, :supplier, :composition, :weight,
                        :category, :metadata::jsonb
                    )
                    ON CONFLICT (fabric_code) DO NOTHING
                    RETURNING id
                """)

                result = await conn.execute(query, {
                    'fabric_code': fabric_code,
                    'name': name,
                    'supplier': supplier,
                    'composition': composition,
                    'weight': weight,
                    'category': category,
                    'metadata': json.dumps(additional_metadata)
                })

                if result.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1

            except Exception as e:
                print(f"❌ Error importing {fabric.get('reference')}: {e}")
                skipped += 1

        print(f"\n✅ Import complete!")
        print(f"   Inserted: {inserted}")
        print(f"   Skipped: {skipped}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(import_fabrics())
```

### 3.3 Import ausführen

```bash
# Script ausführen
python scripts/import_fabrics_to_db.py

# Erwartete Ausgabe:
# 📦 Found 140 fabrics in JSON
# ✅ Import complete!
#    Inserted: 140
#    Skipped: 0
```

### 3.4 Import verifizieren

```bash
# Anzahl Stoffe in DB prüfen
python scripts/inspect_db.py

# Oder direkt in psql:
psql -U henk_user -d henk_rag -c "SELECT COUNT(*) FROM fabrics;"
```

**✅ Checkpoint:** Alle Fabrics in Datenbank importiert

---

## 🔮 SCHRITT 4: Embeddings generieren

### 4.1 Embedding-Script testen (DRY RUN)

```bash
# Zuerst Dry Run (keine DB-Änderungen)
python scripts/generate_fabric_embeddings.py --dry-run --batch-size 10

# Erwartete Ausgabe:
# 🚀 FABRIC EMBEDDINGS GENERATOR
# Model: text-embedding-3-small
# Dimensions: 384
# 📊 Total fabrics in database: 140
# 🏃 DRY RUN MODE - No data will be inserted
```

### 4.2 Embeddings generieren (ECHT)

```bash
# Echte Generierung starten
python scripts/generate_fabric_embeddings.py --batch-size 50

# Dauert ca. 2-3 Minuten für 140 Stoffe
# Erwartete Ausgabe:
# ✅ GENERATION COMPLETE
# Fabrics Processed: 140
# Chunks Created: 560 (140 × 4 Chunks)
# Embeddings Generated: 560
# Total Tokens Used: ~168,000
# Estimated Cost: $0.0034
```

### 4.3 Embeddings verifizieren

```bash
# Dimensionen prüfen
python scripts/verify_embeddings.py

# Erwartete Ausgabe:
# 🔬 EMBEDDING DIMENSIONEN ÜBERPRÜFUNG
# ✅ fabric_embeddings.embedding: 384 Dimensionen
# ✅ Alle Embedding-Dimensionen sind korrekt!
```

**✅ Checkpoint:** Embeddings generiert und verifiziert

---

## 🧪 SCHRITT 5: RAG-System testen

### 5.1 Test-Script erstellen

```bash
nano scripts/test_rag_queries.py
```

**Inhalt:**

```python
"""Test RAG queries with fabric embeddings"""

import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
import openai

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

async def test_rag_query(query_text: str, top_k: int = 5):
    """Test a RAG query."""

    # Generate query embedding
    print(f"\n🔍 Query: {query_text}")
    response = await asyncio.to_thread(
        openai.embeddings.create,
        input=query_text,
        model="text-embedding-3-small",
        dimensions=384
    )
    query_embedding = response.data[0].embedding

    # Search in database
    connection_string = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(connection_string, echo=False)

    async with engine.begin() as conn:
        # Get raw asyncpg connection for vector operations
        raw_conn = await conn.get_raw_connection()
        async_conn = raw_conn.driver_connection

        # Vector similarity search
        query = """
            SELECT
                fe.content,
                fe.chunk_type,
                f.fabric_code,
                f.supplier,
                f.category,
                1 - (fe.embedding <=> $1::vector) as similarity
            FROM fabric_embeddings fe
            JOIN fabrics f ON fe.fabric_id = f.id
            ORDER BY fe.embedding <=> $1::vector
            LIMIT $2
        """

        rows = await async_conn.fetch(query, str(query_embedding), top_k)

        print(f"\n📊 Top {top_k} Results:")
        for i, row in enumerate(rows, 1):
            print(f"\n{i}. {row['fabric_code']} - {row['supplier']}")
            print(f"   Type: {row['chunk_type']}")
            print(f"   Similarity: {row['similarity']:.4f}")
            print(f"   Content: {row['content'][:100]}...")

    await engine.dispose()

async def main():
    """Run test queries."""

    test_queries = [
        "Zeige mir Premium Anzug-Stoffe für Business",
        "Ich brauche einen leichten Stoff für den Sommer",
        "Welche dunkelblauen Stoffe gibt es?",
        "100% Wolle für einen formellen Anzug"
    ]

    for query in test_queries:
        await test_rag_query(query, top_k=3)
        print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(main())
```

### 5.2 RAG-Tests ausführen

```bash
python scripts/test_rag_queries.py

# Erwartete Ausgabe:
# 🔍 Query: Zeige mir Premium Anzug-Stoffe für Business
# 📊 Top 3 Results:
# 1. 695.401/18 - VITALE BARBERIS
#    Type: characteristics
#    Similarity: 0.8234
#    Content: Tela Rustica - 100% Virgin Wool, 250 gr/ml...
```

**✅ Checkpoint:** RAG-System funktioniert!

---

## 📂 SCHRITT 6: Fehlende Kataloge vorbereiten

### 6.1 Hemden-Stoffe Import (WENN VERFÜGBAR)

```bash
# Falls Hemden-Stoffe als JSON/CSV vorhanden:

# 1. Datei in drive_mirror/henk/shirts/ kopieren
cp /pfad/zu/hemden_stoffe.json drive_mirror/henk/shirts/

# 2. Import-Script anpassen (siehe import_fabrics_to_db.py)
# 3. Importieren
# 4. Embeddings generieren
```

### 6.2 Google Drive Credentials einrichten

```bash
# 1. Credentials-Ordner erstellen
mkdir -p credentials

# 2. Google Service Account JSON kopieren
# (von Smartphone-Notizen oder Google Cloud Console)
nano credentials/google_drive_credentials.json

# Inhalt:
# {
#   "type": "service_account",
#   "project_id": "...",
#   "private_key_id": "...",
#   "private_key": "...",
#   ...
# }

# 3. In .env eintragen
# GOOGLE_DRIVE_CREDENTIALS_PATH=./credentials/google_drive_credentials.json
```

### 6.3 Google Drive Sync testen

```bash
# Prerequisites installieren
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

# Sync-Script testen
python scripts/sync_google_drive_pricing.py

# Erwartete Ausgabe:
# ✅ Authenticated with Google Drive
# 📁 Searching for: price_book_by_tier.json
# ✅ Download complete!
```

**✅ Checkpoint:** Google Drive Zugriff funktioniert

---

## 🤖 SCHRITT 7: Agent-Prompts integrieren

### 7.1 Prompt-Loader erstellen

```bash
nano agents/prompt_loader.py
```

**Inhalt:**

```python
"""Load prompts from Promt/ directory."""

from pathlib import Path
from typing import Dict

PROMPT_DIR = Path(__file__).parent.parent / "Promt"

def load_prompt(filename: str) -> str:
    """Load a prompt file."""
    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {filename}")

    return path.read_text(encoding='utf-8')

def load_all_prompts() -> Dict[str, str]:
    """Load all prompts."""
    return {
        "core": load_prompt("henk_core_prompt_optimized.txt"),
        "henk1": load_prompt("henk1_prompt.txt"),
        "henk2": load_prompt("henk2_prompt_drive_style.txt"),
        "henk3": load_prompt("henk3_prompt_measurement.txt")
    }

# Singleton
_PROMPTS = None

def get_prompts() -> Dict[str, str]:
    """Get cached prompts."""
    global _PROMPTS
    if _PROMPTS is None:
        _PROMPTS = load_all_prompts()
    return _PROMPTS
```

### 7.2 HENK1 Agent aktualisieren

```bash
# Backup erstellen
cp agents/henk1.py agents/henk1.py.backup

# Editieren
nano agents/henk1.py
```

**Änderungen:**

```python
# Am Anfang hinzufügen:
from agents.prompt_loader import get_prompts

class Henk1Agent(BaseAgent):
    def __init__(self):
        super().__init__("henk1")
        # Prompts laden
        prompts = get_prompts()
        self.system_prompt = prompts["core"] + "\n\n" + prompts["henk1"]

    async def process(self, state: SessionState) -> AgentDecision:
        # Nutze self.system_prompt für LLM-Calls
        # ...
```

**✅ Checkpoint:** Prompts sind in Agents integriert

---

## 🧹 SCHRITT 8: Code aufräumen

### 8.1 Formatierung prüfen

```bash
# Black
black . --check

# Falls Fehler:
black .

# Ruff
ruff check .

# Auto-Fix:
ruff check . --fix
```

### 8.2 Tests ausführen

```bash
# Workflow-Test
python tests/test_workflow.py

# Erwartete Ausgabe:
# ✅ Workflow completed successfully
```

**✅ Checkpoint:** Code ist sauber

---

## 📝 SCHRITT 9: Dokumentation aktualisieren

### 9.1 README.md

```bash
# Status-Update in README.md

## 🎯 Current Status (2025-12-08)

- ✅ 140 Anzug-Stoffe in Datenbank
- ✅ Fabric Embeddings (384 dims) generiert
- ✅ RAG-System funktioniert
- ✅ Agent-Prompts integriert
- ⏳ Hemden-Stoffe (Import pending)
- ⏳ Kataloge (Templates vorhanden)
```

### 9.2 CLEANUP_SUMMARY.md aktualisieren

```bash
nano CLEANUP_SUMMARY.md

# Ergänze:
## 🎯 Erfolge (2025-12-08 Abend)

- ✅ .env Secrets konfiguriert
- ✅ PostgreSQL Datenbank setup
- ✅ 140 Fabrics importiert
- ✅ 560 Embeddings generiert
- ✅ RAG-System validiert
- ✅ Prompts integriert
```

**✅ Checkpoint:** Dokumentation aktuell

---

## 🚀 SCHRITT 10: Git Commit & Push

### 10.1 Status prüfen

```bash
git status
```

### 10.2 Änderungen committen

```bash
# Alle hinzufügen
git add .

# Commit
git commit -m "$(cat <<'EOF'
feat: Database setup, fabric import and RAG validation

### Database Setup
- PostgreSQL database henk_rag created
- pgvector extension enabled
- fabrics and fabric_embeddings tables created

### Fabric Import
- Import 140 fabrics from fabric_catalog.json
- Import script: scripts/import_fabrics_to_db.py
- All fabrics with metadata in database

### Embeddings
- Generate 560 embeddings (140 fabrics × 4 chunks)
- OpenAI text-embedding-3-small (384 dims)
- Cost: ~$0.0034

### RAG System
- RAG queries functional
- Vector similarity search working
- Test script: scripts/test_rag_queries.py

### Prompts Integration
- Prompt loader created: agents/prompt_loader.py
- HENK1/2/3 prompts integrated
- System prompts loaded from Promt/ directory

### Environment
- .env secrets configured
- Database credentials set
- OpenAI API key added

### Documentation
- README.md updated with current status
- CLEANUP_SUMMARY.md updated
- TODO lists created (smartphone + PC)
EOF
)"
```

### 10.3 Pushen

```bash
# Push to branch
git push -u origin claude/cleanup-env-update-015fjKQAyboTrWdrE5hNviSs
```

**✅ Checkpoint:** Alles committed und gepusht

---

## ✅ FERTIG! - Tages-Zusammenfassung

### Was heute erreicht wurde:

1. ✅ **Environment konfiguriert** - Alle Secrets in .env
2. ✅ **Datenbank setup** - PostgreSQL mit pgvector
3. ✅ **140 Stoffe importiert** - Von JSON in DB
4. ✅ **560 Embeddings generiert** - RAG-ready
5. ✅ **RAG-System validiert** - Queries funktionieren
6. ✅ **Prompts integriert** - HENK1/2/3 laden Prompts
7. ✅ **Code formatiert** - Black + Ruff clean
8. ✅ **Dokumentiert** - README & Summaries aktuell
9. ✅ **Git committed** - Alles gesichert

### Was noch fehlt (für später):

- ⏳ **~1.860 Hemden-Stoffe** - Quelle identifizieren & importieren
- ⏳ **Kataloge befüllen** - Garments, Options, Style
- ⏳ **Google Drive Sync** - Automatisieren
- ⏳ **Agent-Tests** - Integration Tests erweitern
- ⏳ **Pipedrive Integration** - CRM anbinden

---

## 🎯 Morgen weitermachen:

1. Hemden-Stoffe aus Google Drive holen
2. Import-Script für Hemden anpassen
3. Kataloge mit Daten befüllen
4. Weitere Embeddings generieren
5. End-to-End Test: HENK1 → HENK2 → HENK3

---

**Version**: 1.0
**Datum**: 2025-12-08
**Geschätzte Dauer**: 3-4 Stunden
**Status**: ✅ READY TO EXECUTE
