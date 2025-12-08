# 🚀 Quick Start - Laserhenk testen

## Aktuelle Situation

✅ **Funktioniert:**
- JSON-Dateien sind valide
- Fabric-Katalog mit 140 Fabrics vorhanden
- Repository-Struktur ist sauber

⚠️ **Benötigt Setup:**
- Python-Abhängigkeiten installieren
- `.env` Datei erstellen
- Datenbank konfigurieren

❌ **Fehlt noch:**
- Garment/Shirt/Options/Style Kataloge

---

## 🔧 Setup in 3 Schritten

### Schritt 1: Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### Schritt 2: .env Datei erstellen

```bash
# Kopiere das Beispiel
cp .env.example .env

# Bearbeite .env und füge hinzu:
# - DATABASE_URL=postgresql://user:pass@host:port/dbname
# - OPENAI_API_KEY=sk-...
# - EMBEDDING_DIMENSION=384
```

**Benötigte Umgebungsvariablen:**
```env
# Datenbank (PostgreSQL mit pgvector Extension)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/laserhenk
# Oder alternativ:
POSTGRES_CONNECTION_STRING=postgresql://user:password@localhost:5432/laserhenk

# OpenAI API
OPENAI_API_KEY=sk-your-api-key-here

# Embedding-Konfiguration
EMBEDDING_DIMENSION=384
EMBEDDING_MODEL=text-embedding-3-small
```

### Schritt 3: Datenbank vorbereiten

```bash
# Prüfe Datenbankverbindung
python scripts/inspect_db.py

# Verifiziere Embedding-Dimensionen
python scripts/verify_embeddings.py
```

---

## ✅ Was Sie JETZT testen können

### Test 1: JSON-Daten validieren
```bash
# Alle JSON-Dateien prüfen
python3 -m json.tool drive_mirror/henk/fabrics/fabric_catalog.json | head
python3 -m json.tool drive_mirror/henk/fabrics/price_book_by_tier.json
```

### Test 2: Fabric-Embeddings generieren
```bash
# Generiere Embeddings für Fabric-Katalog
python scripts/generate_fabric_embeddings.py
```

**Was passiert:**
- Liest `fabric_catalog.json` (140 Fabrics)
- Generiert Embeddings via OpenAI
- Speichert in PostgreSQL mit pgvector

### Test 3: Workflow-Test (eingeschränkt)
```bash
# Test-Workflow ausführen
python tests/test_workflow.py
```

**Was passiert:**
- Initialisiert Graph-State
- Startet Operator-Agent
- Stoppt nach 10 Steps (Infinite-Loop-Protection)

### Test 4: RAG-Query testen (nur Fabrics)
```bash
# Prüfe ob RAG-Tool funktioniert
python -c "
from tools.rag_tool import RAGTool
from models.tools import RAGQuery
import asyncio

async def test():
    rag = RAGTool()
    query = RAGQuery(query='blaue Wolle', top_k=3)
    result = await rag.query(query)
    print(f'Gefunden: {len(result.results)} Fabrics')
    for r in result.results:
        print(f'  - {r}')

asyncio.run(test())
"
```

---

## ❌ Was NICHT funktioniert (noch)

### Fehlende Kataloge
- **Garment-Katalog** → RAG-Queries für Kleidungsstücke geben leere Ergebnisse
- **Shirt-Katalog** → Keine Hemd-Konfigurationen verfügbar
- **Options-Katalog** → Keine Maßkonfektion-Optionen
- **Style-Katalog** → Design-Henk hat keine Style-Informationen

### Auswirkung auf Agents
- **Henk1 Agent**: Funktioniert nur mit Fabric-Daten
- **Design-Henk Agent**: Keine Style-Empfehlungen möglich
- **Laserhenk Agent**: Eingeschränkte Funktionalität

---

## 📊 Test-Status-Matrix

| Test | Status | Benötigt | Kommentar |
|------|--------|----------|-----------|
| JSON-Validierung | ✅ | Nichts | Alle JSON-Dateien valide |
| Python-Pakete | ⚠️ | `pip install` | requirements.txt vorhanden |
| .env Konfiguration | ⚠️ | Manuelle Erstellung | .env.example als Vorlage |
| Datenbankverbindung | ⚠️ | PostgreSQL + .env | pgvector Extension nötig |
| Fabric-Embeddings | ⚠️ | OpenAI API Key | Nur wenn DB + .env fertig |
| RAG-Queries (Fabrics) | ⚠️ | Embeddings in DB | Funktioniert nach Schritt 2+3 |
| Workflow-Test | ⚠️ | Alle Dependencies | Eingeschränkt ohne alle Kataloge |
| End-to-End Test | ❌ | Alle Kataloge | Kataloge fehlen noch |

---

## 🎯 Empfohlene Test-Reihenfolge

### Phase 1: Setup (heute möglich) ✅
1. ✅ Dependencies installieren
2. ✅ .env erstellen und konfigurieren
3. ✅ Datenbankverbindung testen
4. ✅ Fabric-Embeddings generieren
5. ✅ RAG-Query für Fabrics testen

### Phase 2: Daten ergänzen (morgen) 🟡
6. Garment-Katalog erstellen
7. Shirt-Katalog erstellen
8. Options-Katalog erstellen
9. Style-Katalog erstellen
10. Alle Embeddings generieren

### Phase 3: Integration (übermorgen) 🟠
11. Vollständiger Workflow-Test
12. Agent-Interaktionen testen
13. End-to-End Szenarien

---

## 💡 Tipps

### Wenn Sie keine Datenbank haben
```bash
# Docker PostgreSQL mit pgvector
docker run -d \
  --name laserhenk-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=laserhenk \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# .env dann:
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/laserhenk
```

### Wenn Sie keinen OpenAI API Key haben
- ⚠️ RAG-Tool und Embeddings funktionieren nicht
- ✅ JSON-Validierung und Struktur-Tests funktionieren trotzdem
- ✅ Workflow-Code kann gelesen/geprüft werden

### Minimaler Test ohne Setup
```bash
# Nur JSON und Struktur prüfen
python3 -m json.tool drive_mirror/henk/fabrics/fabric_catalog.json > /dev/null && echo "✅ OK"
ls -la scripts/ tests/ agents/ models/ workflow/
```

---

## 📞 Support

Bei Problemen:
1. Prüfe `CLEANUP_SUMMARY.md` für Details zum letzten Cleanup
2. Prüfe `TEST_GUIDE.md` für ausführliche Test-Anleitung
3. Prüfe Logs in der Konsole

