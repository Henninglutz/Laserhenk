# 🧪 Test-Anleitung für Laserhenk

## Voraussetzungen prüfen

### 1. Python-Umgebung
```bash
python3 --version  # Sollte >= 3.10 sein
```

### 2. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

### 3. Umgebungsvariablen prüfen
```bash
# .env Datei muss existieren
ls -la .env

# Benötigte Variablen:
# - DATABASE_URL oder POSTGRES_CONNECTION_STRING
# - OPENAI_API_KEY
# - EMBEDDING_DIMENSION (default: 384)
```

## Was kann JETZT getestet werden? ✅

### Test 1: JSON-Validierung
```bash
# Prüfe ob JSON-Dateien valide sind
python3 -m json.tool drive_mirror/henk/fabrics/fabric_catalog.json > /dev/null && echo "✅ fabric_catalog.json OK"
python3 -m json.tool drive_mirror/henk/fabrics/price_book_by_tier.json > /dev/null && echo "✅ price_book_by_tier.json OK"
```

### Test 2: Datenbankverbindung
```bash
# Prüfe DB-Verbindung (benötigt .env)
python scripts/inspect_db.py
```

### Test 3: Embedding-Dimensionen
```bash
# Prüfe Embedding-Dimensionen in DB
python scripts/verify_embeddings.py
```

### Test 4: Fabric-Embeddings generieren
```bash
# Generiere Embeddings für Fabric-Katalog (benötigt OpenAI API Key)
python scripts/generate_fabric_embeddings.py
```

### Test 5: Workflow-Test (eingeschränkt)
```bash
# Test-Workflow ausführen (wird nach 10 Steps stoppen)
python tests/test_workflow.py
```

## Was funktioniert NOCH NICHT? ❌

### Fehlende Daten
- ❌ **Garment-Katalog** - keine Daten vorhanden
- ❌ **Shirt-Katalog** - keine Daten vorhanden  
- ❌ **Options-Katalog** - keine Daten vorhanden
- ❌ **Style-Katalog** - keine Daten vorhanden

### Auswirkungen
- RAG-Queries für Garments/Shirts/Options/Styles werden LEER zurückgeben
- Design-Henk Agent hat keine Style-Informationen
- Henk1 Agent hat eingeschränkte Produkt-Informationen

## Empfohlene Test-Reihenfolge

### 🟢 Phase 1: Basis-Tests (JETZT möglich)
1. JSON-Validierung ✅
2. Datenbankverbindung prüfen
3. Embedding-Dimensionen verifizieren
4. Fabric-Embeddings generieren

### 🟡 Phase 2: Nach Daten-Ergänzung (TODO)
5. Alle Kataloge erstellen (siehe CLEANUP_SUMMARY.md)
6. Alle Embeddings generieren
7. RAG-Queries für jeden Katalog testen

### 🟠 Phase 3: Integration-Tests
8. Vollständiger Workflow-Test
9. Agent-Interaktion testen
10. End-to-End Szenario

## Schnelltest-Script

```bash
#!/bin/bash
echo "=== LASERHENK QUICK TEST ==="
echo ""

# Test 1: JSON
echo "1. JSON-Dateien..."
python3 -m json.tool drive_mirror/henk/fabrics/fabric_catalog.json > /dev/null 2>&1 && echo "   ✅ fabric_catalog.json" || echo "   ❌ fabric_catalog.json"
python3 -m json.tool drive_mirror/henk/fabrics/price_book_by_tier.json > /dev/null 2>&1 && echo "   ✅ price_book_by_tier.json" || echo "   ❌ price_book_by_tier.json"

# Test 2: .env
echo ""
echo "2. Konfiguration..."
[ -f .env ] && echo "   ✅ .env existiert" || echo "   ❌ .env fehlt"

# Test 3: Dependencies
echo ""
echo "3. Python-Pakete..."
python3 -c "import langgraph, langchain, pydantic" 2>/dev/null && echo "   ✅ Abhängigkeiten installiert" || echo "   ❌ Abhängigkeiten fehlen (pip install -r requirements.txt)"

# Test 4: Scripts
echo ""
echo "4. Scripts..."
[ -f scripts/verify_embeddings.py ] && echo "   ✅ verify_embeddings.py" || echo "   ❌ verify_embeddings.py fehlt"
[ -f scripts/generate_fabric_embeddings.py ] && echo "   ✅ generate_fabric_embeddings.py" || echo "   ❌ generate_fabric_embeddings.py fehlt"
[ -f tests/test_workflow.py ] && echo "   ✅ test_workflow.py" || echo "   ❌ test_workflow.py fehlt"

echo ""
echo "=== TEST ABGESCHLOSSEN ==="
```

## Kurzer manueller Check (Supervisor + Schnitt-Loop)
1. Server starten: `python run_flask.py`
2. Chat posten:
   ```bash
   curl -X POST http://localhost:3000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id":"demo","message":"Zweiteiler ohne Weste"}'
   ```
3. Erwartung:
   - Keine 500er im Log, selbst wenn das Supervisor-LLM kein JSON liefert.
   - SessionState enthält `suit_parts="2"`, `wants_vest=false`, `henk1_cut_confirmed=true` und es folgt keine erneute 2/3-Teiler-Rückfrage.
