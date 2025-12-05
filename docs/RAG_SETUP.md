# RAG Database Setup Guide

## 🎯 Übersicht

Das HENK System nutzt PostgreSQL mit pgvector für RAG (Retrieval-Augmented Generation).
Die Datenbank speichert:
- **Stoffe** (fabrics) mit Embeddings für Semantic Search
- **Moodboards** und Style-Referenzen
- **Kundendaten** (optional, CRM-Integration)

---

## 📋 Voraussetzungen

1. **PostgreSQL 15+** installiert
2. **pgvector Extension** installiert
3. Python Dependencies: `psycopg2-binary`, `sqlalchemy`

---

## 🚀 Installation

### 1. PostgreSQL installieren (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### 2. pgvector Extension installieren

```bash
# Clone pgvector repo
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

# Compile and install
make
sudo make install
```

### 3. Datenbank erstellen

```bash
sudo -u postgres psql

# In psql:
CREATE DATABASE henk_rag;
CREATE USER henk_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE henk_rag TO henk_user;

# Exit psql
\q
```

### 4. pgvector Extension aktivieren

```bash
psql -U henk_user -d henk_rag

# In psql:
CREATE EXTENSION IF NOT EXISTS vector;

# Verify
SELECT * FROM pg_extension WHERE extname = 'vector';

\q
```

---

## 🗄️ Schema Setup

### Fabrics Table

```sql
CREATE TABLE fabrics (
    id SERIAL PRIMARY KEY,
    fabric_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,

    -- Material Properties
    material VARCHAR(100),           -- e.g., "Wool", "Wool/Silk Blend"
    weight INTEGER,                  -- in g/m²
    pattern VARCHAR(100),            -- e.g., "Pinstripe", "Solid"
    color_primary VARCHAR(50),
    color_secondary VARCHAR(50),

    -- Seasonal
    season VARCHAR(20),              -- "Spring/Summer", "Fall/Winter", "All-Season"

    -- Pricing & Availability
    price_tier VARCHAR(20),          -- "standard", "premium", "luxury"
    base_price DECIMAL(10,2),
    stock_status VARCHAR(20) DEFAULT 'in_stock',

    -- RAG Embeddings (OpenAI text-embedding-3-small = 1536 dimensions)
    description_embedding vector(1536),

    -- Metadata
    supplier VARCHAR(100),
    origin_country VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Indexes
    INDEX idx_fabric_code (fabric_code),
    INDEX idx_pattern (pattern),
    INDEX idx_season (season),
    INDEX idx_price_tier (price_tier)
);

-- Vector similarity index (HNSW for performance)
CREATE INDEX ON fabrics USING hnsw (description_embedding vector_cosine_ops);
```

### Moodboards Table

```sql
CREATE TABLE moodboards (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Categories
    style_tags TEXT[],               -- e.g., ["business", "wedding", "casual"]
    occasion VARCHAR(100),
    season VARCHAR(20),

    -- Assets
    image_urls TEXT[],

    -- RAG Embedding
    description_embedding vector(1536),

    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_occasion (occasion),
    INDEX idx_season (season)
);

CREATE INDEX ON moodboards USING hnsw (description_embedding vector_cosine_ops);
```

---

## ⚙️ Configuration

### 1. Update .env

```bash
cp .env.example .env
```

Edit `.env`:

```env
# PostgreSQL RAG Database
POSTGRES_CONNECTION_STRING=postgresql://henk_user:your_secure_password@localhost:5432/henk_rag
```

### 2. Test Connection

```python
from config.settings import get_settings
import psycopg2

settings = get_settings()
conn = psycopg2.connect(settings.postgres_connection_string)
print("✅ Database connection successful!")
conn.close()
```

---

## 📦 Data Import

### Import Fabrics from JSON

Wenn du Stoff-Daten in `drive_mirror/henk/fabrics/fabric_catalog.json` hast:

```python
import asyncio
from tools.rag_tool import RAGTool
import json

async def import_fabrics():
    rag = RAGTool()

    with open("drive_mirror/henk/fabrics/fabric_catalog.json") as f:
        fabrics = json.load(f)

    for fabric in fabrics:
        await rag.insert_fabric(fabric)

    print(f"✅ Imported {len(fabrics)} fabrics")

asyncio.run(import_fabrics())
```

---

## 🧪 Testing RAG Tool

```python
import asyncio
from tools.rag_tool import RAGTool

async def test_rag():
    rag = RAGTool()

    # Test fabric search
    results = await rag.search(
        query="navy blue wool for business suit",
        fabric_type="wool",
        top_k=5
    )

    print(f"Found {len(results)} matching fabrics")
    for r in results[:3]:
        print(f"- {r['name']} ({r['fabric_code']})")

asyncio.run(test_rag())
```

---

## 🔧 Troubleshooting

### Connection Failed

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Check if port 5432 is open
sudo netstat -plnt | grep 5432
```

### pgvector not found

```bash
# Verify extension
psql -U henk_user -d henk_rag -c "SELECT * FROM pg_extension WHERE extname = 'vector';"

# If missing, reinstall
cd pgvector && sudo make install
```

### Permission Denied

```bash
# Grant permissions
sudo -u postgres psql -d henk_rag -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO henk_user;"
```

---

## 📚 Next Steps

1. **Import initial data** (fabrics, moodboards)
2. **Generate embeddings** for all texts
3. **Test semantic search** functionality
4. **Monitor performance** (query times should be <100ms)

---

## 🛠️ Advanced: Docker Setup (Optional)

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: henk_rag
      POSTGRES_USER: henk_user
      POSTGRES_PASSWORD: your_secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Start:
```bash
docker-compose up -d
```

---

**Status:** 🟡 Setup required - follow steps above to activate RAG functionality.
