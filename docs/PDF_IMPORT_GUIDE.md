# 📄 PDF Import Guide - Hemden, Styles & Preise

Anleitung zum Importieren von PDF-Dokumentation in die RAG-Datenbank.

---

## 🎯 Übersicht

Workflow:
1. **PDF → JSON**: Text extrahieren und chunken
2. **JSON → RAG DB**: Embeddings generieren und importieren
3. **Verifizieren**: RAG-Suche testen

---

## 📋 Voraussetzungen

### 1. Python Packages installieren

```bash
pip install pdfplumber pypdf2
```

### 2. PDF-Struktur vorbereiten

```bash
# Ordner für PDFs erstellen
mkdir -p docs/source_pdfs

# PDFs kopieren
cp ~/Downloads/hemden_katalog.pdf docs/source_pdfs/
cp ~/Downloads/style_guide.pdf docs/source_pdfs/
cp ~/Downloads/preisliste_2024.pdf docs/source_pdfs/
```

---

## 🔄 Workflow: PDF → RAG Database

### SCHRITT 1: PDF zu JSON extrahieren

#### Hemden-Katalog

```bash
python scripts/extract_pdf_to_json.py \
  --input docs/source_pdfs/hemden_katalog.pdf \
  --output drive_mirror/henk/shirts/hemden_chunks.json \
  --category shirts \
  --chunk-size 500 \
  --detect-sections

# Erwartete Ausgabe:
# ======================================================================
# 📄 PDF EXTRACTION TO JSON
# ======================================================================
# Input: docs/source_pdfs/hemden_katalog.pdf
# Output: drive_mirror/henk/shirts/hemden_chunks.json
# Category: shirts
# Chunk Size: 500
#
# 📄 Lese PDF: docs/source_pdfs/hemden_katalog.pdf
#    Seiten: 25
# ✅ Text extrahiert: 12,450 Zeichen
#
# 🔍 Erkenne Sections...
# ✅ Gefunden: 8 Sections
#    - kragenformen
#    - manschettentypen
#    - stoffqualitaeten
#    - passform
#    ...
#
# 🔪 Chunking Text (max 500 chars pro Chunk)...
# ✅ Erstellt: 28 Chunks
#
# ✅ JSON gespeichert: drive_mirror/henk/shirts/hemden_chunks.json
#    Total Chunks: 28
#    Durchschnitt: 444 chars pro Chunk
#
# 🎯 Nächster Schritt:
#    python scripts/import_json_to_rag.py --input drive_mirror/henk/shirts/hemden_chunks.json
```

#### Style Guide

```bash
python scripts/extract_pdf_to_json.py \
  --input docs/source_pdfs/style_guide.pdf \
  --output drive_mirror/henk/knowledge/style_chunks.json \
  --category styles \
  --chunk-size 600
```

#### Preisliste

```bash
python scripts/extract_pdf_to_json.py \
  --input docs/source_pdfs/preisliste_2024.pdf \
  --output drive_mirror/henk/pricing/pricing_chunks.json \
  --category pricing \
  --chunk-size 400
```

---

### SCHRITT 2: JSON in RAG-Datenbank importieren

#### Hemden-Chunks importieren

```bash
python scripts/import_json_to_rag.py \
  --input drive_mirror/henk/shirts/hemden_chunks.json \
  --batch-size 20

# Erwartete Ausgabe:
# ======================================================================
# 📥 JSON CHUNKS TO RAG DATABASE IMPORT
# ======================================================================
# Input: drive_mirror/henk/shirts/hemden_chunks.json
# Batch Size: 20
# Model: text-embedding-3-small
# Dimensions: 1536
#
# ✅ Database connection established
# 📊 Geladen: 28 Chunks
#    Category: shirts
#    Total Chars: 12,450
#
# 🔮 Importiere 28 Chunks...
#
# --- Batch 1 (Chunks 1-20) ---
# 📦 Processing 20 chunks...
# 🔮 Generating 20 embeddings...
# 💾 Inserting 20 chunks into rag_docs...
# ✅ Batch complete: 20 chunks, 20 embeddings
# 📈 Progress: 71.4% (20/28)
#
# --- Batch 2 (Chunks 21-28) ---
# 📦 Processing 8 chunks...
# 🔮 Generating 8 embeddings...
# 💾 Inserting 8 chunks into rag_docs...
# ✅ Batch complete: 8 chunks, 8 embeddings
# 📈 Progress: 100.0% (28/28)
#
# ======================================================================
# ✅ IMPORT COMPLETE
# ======================================================================
# Chunks Processed: 28
# Embeddings Generated: 28
# Inserted to DB: 28
# Errors: 0
# ======================================================================
```

#### Style & Pricing importieren

```bash
# Style Guide
python scripts/import_json_to_rag.py \
  --input drive_mirror/henk/knowledge/style_chunks.json \
  --batch-size 20

# Preisliste
python scripts/import_json_to_rag.py \
  --input drive_mirror/henk/pricing/pricing_chunks.json \
  --batch-size 20
```

---

## ✅ SCHRITT 3: RAG-Suche testen

### Mit psql prüfen

```bash
psql -U henk_user -d henk_rag -c "
SELECT category, COUNT(*) as chunks
FROM rag_docs
GROUP BY category
ORDER BY category;
"

# Erwartete Ausgabe:
#  category  | chunks
# -----------+--------
#  fabrics   |    483
#  pricing   |     45
#  shirts    |     28
#  styles    |     62
# (4 rows)
```

### RAG-Query testen

```python
# Test in Python
import asyncio
from tools.rag_tool import RAGTool

async def test():
    rag = RAGTool()

    # Test Hemden-Query
    results = await rag.search_knowledge(
        query="Welche Kragenformen gibt es für Business Hemden?",
        category="shirts",
        top_k=3
    )

    for r in results:
        print(f"Score: {r['similarity']:.3f}")
        print(f"Content: {r['content'][:100]}...")
        print()

asyncio.run(test())
```

---

## 💡 Tipps & Best Practices

### PDF-Qualität optimieren

**Wenn PDFs gescannt sind (keine Text-Ebene):**
1. Adobe Acrobat: Tools → Text Recognition → In This File
2. Online OCR: https://www.onlineocr.net/
3. CLI Tool: `ocrmypdf input.pdf output.pdf`

**Tabellen extrahieren:**
- pdfplumber kann Tabellen erkennen: `--detect-tables` Flag (TODO)
- Alternative: Tabelle manuell in CSV umwandeln

### Chunk-Size Empfehlungen

| Content Type | Chunk Size | Warum |
|--------------|-----------|-------|
| Hemden-Specs | 400-600 | Kompakte Produktinfos |
| Style-Regeln | 600-800 | Zusammenhängende Erklärungen |
| Preislisten  | 300-500 | Tabellen & Listen |
| Technische Docs | 800-1000 | Detaillierte Beschreibungen |

### Kategorien

- `shirts` - Hemden-Optionen, Kragen, Manschetten, Fit
- `styles` - Dress Codes, Farb-Kombinationen, Style-Rules
- `pricing` - Preise, Kategorien, Aufpreise
- `fabrics` - Stoff-Details (bereits vorhanden)
- `measurements` - Maßtabellen, Größen (TODO)

---

## 🔧 Troubleshooting

### Problem: "pdfplumber not found"
```bash
pip install pdfplumber
```

### Problem: "Text ist unleserlich / falsche Zeichen"
- PDF hat falsche Encoding
- Lösung: `--encoding utf-8` Flag (TODO)

### Problem: "Embedding Fehler 429 (Rate Limit)"
- OpenAI Rate Limit erreicht
- Lösung: `--batch-size 10` (kleinere Batches)
- Oder: Warte 60 Sekunden

### Problem: "Database connection failed"
- PostgreSQL läuft nicht
- Lösung: Starte PostgreSQL oder prüfe .env

---

## 📊 Kosten-Schätzung

**Hemden-Katalog (25 Seiten):**
- ~12,000 Zeichen = ~3,000 Tokens
- 28 Chunks × 1536 dims
- **Kosten: ~$0.00006** (0.006 Cent!)

**Style Guide (40 Seiten):**
- ~20,000 Zeichen = ~5,000 Tokens
- 50 Chunks × 1536 dims
- **Kosten: ~$0.0001** (0.01 Cent!)

**Preisliste (10 Seiten):**
- ~5,000 Zeichen = ~1,250 Tokens
- 15 Chunks × 1536 dims
- **Kosten: ~$0.000025** (0.0025 Cent!)

**TOTAL: ~$0.0002** (0.02 Cent für alle PDFs!)

---

## 🎯 Nächste Schritte

Nach dem Import:
1. ✅ RAG-Suche testen
2. ✅ HENK2 Agent mit neuen Chunks testen
3. ✅ Style-Empfehlungen validieren
4. ✅ Pricing-Berechnungen integrieren

---

**Version**: 1.0
**Datum**: 2025-12-08
**Status**: ✅ Ready for PDF Import
