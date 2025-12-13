# PostgreSQL Setup für Mac

## 🎯 Schnellste Lösung: Docker Desktop für Mac

### 1. Docker Desktop installieren

Download und installiere Docker Desktop:
👉 **https://www.docker.com/products/docker-desktop/**

Oder via Homebrew:
```bash
brew install --cask docker
```

Nach Installation: **Docker Desktop App starten** (Icon im Dock)

### 2. PostgreSQL starten

Im Terminal (auf deinem Mac):

```bash
cd ~/Laserhenk  # oder wo dein Projekt ist

# PostgreSQL Container starten
docker-compose up -d

# Prüfen ob läuft
docker ps
```

Du solltest sehen:
```
CONTAINER ID   IMAGE                    STATUS
xxx            pgvector/pgvector:pg15   Up
```

### 3. .env Datei erstellen

```bash
cd ~/Laserhenk
cp .env.example .env
```

Dann `.env` editieren und eintragen:

```env
# OpenAI API Key (WICHTIG!)
OPENAI_API_KEY=sk-...  # Dein echter Key hier

# Database Connection (Docker localhost)
POSTGRES_CONNECTION_STRING=postgresql://henk_user:henk_secure_password_2024@localhost:5432/henk_rag
DATABASE_URL=postgresql://henk_user:henk_secure_password_2024@localhost:5432/henk_rag

# LangSmith deaktivieren
LANGCHAIN_TRACING_V2=false

# Embeddings
EMBEDDING_DIMENSION=1536
EMBEDDING_MODEL=text-embedding-3-small
```

### 4. Datenbank-Schema erstellen

```bash
# Python venv aktivieren
source .venv/bin/activate

# Schema-Setup Script ausführen (muss noch erstellt werden)
python scripts/setup_database.py
```

Oder manuell via psql:
```bash
# In Container einloggen
docker exec -it laserhenk_postgres psql -U henk_user -d henk_rag

# Im psql Prompt:
CREATE EXTENSION IF NOT EXISTS vector;

# Schema aus docs/RAG_SETUP.md kopieren und einfügen
# (Zeilen 76-143)
```

### 5. Testdaten importieren (optional)

Falls du Stoffe in der Datenbank brauchst:
```bash
python scripts/import_fabrics.py
```

### 6. Flask starten

```bash
python app.py
```

Jetzt sollte RAG funktionieren! ✅

---

## 🔄 Alternative: Homebrew PostgreSQL (ohne Docker)

Falls du Docker nicht nutzen willst:

```bash
# PostgreSQL installieren
brew install postgresql@15 pgvector

# PostgreSQL starten
brew services start postgresql@15

# Datenbank erstellen
createdb henk_rag

# pgvector Extension
psql henk_rag -c "CREATE EXTENSION vector;"
```

Dann in `.env`:
```env
POSTGRES_CONNECTION_STRING=postgresql://$(whoami)@localhost:5432/henk_rag
DATABASE_URL=postgresql://$(whoami)@localhost:5432/henk_rag
```

---

## ☁️ Alternative: Cloud-Datenbank (Supabase - Kostenlos)

1. Gehe zu **https://supabase.com**
2. Erstelle kostenlosen Account
3. Create new project → "Laserhenk"
4. Warte bis Datenbank bereit ist (1-2 Min)
5. In Supabase Dashboard:
   - Settings → Database
   - Kopiere **Connection String** (Pooling Mode)
6. In SQL Editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

7. In `.env` eintragen:
```env
POSTGRES_CONNECTION_STRING=postgresql://postgres.[projekt-ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
DATABASE_URL=postgresql://postgres.[projekt-ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

---

## 🧪 Verbindung testen

```python
# test_db.py
import asyncpg
import asyncio

async def test():
    conn = await asyncpg.connect(
        'postgresql://henk_user:henk_secure_password_2024@localhost:5432/henk_rag'
    )
    version = await conn.fetchval('SELECT version()')
    print(f"✅ Connected! PostgreSQL version:")
    print(version)
    await conn.close()

asyncio.run(test())
```

```bash
python test_db.py
```

---

## ❓ Troubleshooting

### Port 5432 bereits belegt
```bash
# Welcher Prozess nutzt 5432?
lsof -i :5432

# Anderen PostgreSQL stoppen
brew services stop postgresql
```

### Docker Container startet nicht
```bash
# Logs anschauen
docker-compose logs postgres

# Container neu bauen
docker-compose down
docker-compose up -d --force-recreate
```

### Connection refused
- Docker Desktop läuft?
- Container läuft? (`docker ps`)
- Richtiger Port in .env? (5432)

---

**Empfehlung:** Start with Docker Desktop - einfachste und sauberste Lösung! 🐳
