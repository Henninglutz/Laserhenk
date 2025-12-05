# 🔍 LASERHENK - Datenbank-Analyse & Aktionsplan

**Datum:** 2025-12-05
**Status:** 🔴 Action Required

---

## 📊 Zusammenfassung der Inspektion

### ✅ Was funktioniert:

1. **RAG Grundfunktionalität**
   - `rag_docs`: 483 Dokumente mit Embeddings
   - Enthält: Style-Kataloge, HENK2-Optionen, Shirt-Kataloge
   - Embeddings vorhanden (384 Dimensionen erwartet)
   - ✅ RAG für allgemeine Styling-Fragen funktioniert

2. **Fabrics Tabelle**
   - 1988 Stoffe importiert
   - Vollständige Metadaten (Supplier, Composition, Weight, Color, Pattern)
   - `price_category` Feld vorhanden
   - `additional_metadata.preiskat` enthält Preiskategorien (z.B. '9')

### ❌ Was fehlt:

1. **Fabric Embeddings**
   - `fabric_embeddings` Tabelle ist **LEER** (0 Zeilen)
   - ❌ **Semantic Search für Stoffe funktioniert NICHT**
   - ❌ RAG Tool kann keine Stoffe basierend auf Beschreibungen finden
   - ❌ "Zeig mir navy blue wool for business suit" funktioniert nicht

2. **Pricing Schema**
   - `pricing_rules` Tabelle fehlt komplett
   - Keine `price` oder `price_per_meter` Spalten in `fabrics`
   - `drive_mirror/henk/fabrics/price_book_by_tier.json` ist leer
   - ⚠️ Pricing Tool nutzt Fallback-Preise (nicht stoffspezifisch)

3. **Embedding Dimensionen-Check**
   - Altes Inspektionsskript hatte Fehler (`array_length` statt `vector_dims`)
   - ✅ Korrigiertes Skript erstellt: `verify_embeddings.py`
   - ⏳ Muss noch mit korrekter .env ausgeführt werden

---

## 🎯 Kritische Probleme

### Problem 1: Keine Fabric Embeddings 🔴

**Impact:** HIGH
**Severity:** CRITICAL

**Problem:**
- Die Hauptfunktion des RAG Systems (Fabric-Suche) funktioniert nicht
- User-Anfragen wie "Zeig mir dunkelblaue Stoffe für Hochzeit" können nicht beantwortet werden
- Der RAG Tool ist implementiert, aber die Daten fehlen

**Ursache:**
- Embeddings wurden nie generiert oder Import ist fehlgeschlagen
- `fabric_embeddings` Tabelle existiert, ist aber leer

**Lösung:**
1. Fabric-Beschreibungen aus `fabrics` Tabelle extrahieren
2. Embeddings mit OpenAI `text-embedding-3-small` generieren (384 dimensions)
3. In `fabric_embeddings` speichern mit Chunking-Strategie:
   - Chunk Type 1: **Characteristics** (Composition, Weight, Pattern, Color)
   - Chunk Type 2: **Visual** (Color, Pattern, Texture beschreibend)
   - Chunk Type 3: **Usage** (Category, Season, Occasion)
   - Chunk Type 4: **Technical** (Care Instructions, Origin, Supplier)

**Script erstellen:**
```bash
python scripts/generate_fabric_embeddings.py
```

---

### Problem 2: Kein Pricing Schema 🟡

**Impact:** MEDIUM
**Severity:** HIGH

**Problem:**
- Pricing Tool nutzt Fallback-Hardcoded-Preise
- Keine stoffspezifischen Preise
- `preiskat` in `additional_metadata` wird nicht genutzt
- Google Drive `price_book_by_tier.json` ist leer

**Aktuelles Pricing (Fallback):**
```python
{
    "suit": 1800€,        # 2-Teiler
    "three_piece": 2100€, # 3-Teiler
    "jacket": 1200€,      # Sakko
    "trousers": 600€,     # Hose
    "vest": 400€,         # Weste
    "coat": 2500€,        # Mantel
    "tuxedo": 2200€,      # Smoking
}
```

**Lösung:**

**Option A: Pricing Rules Tabelle erstellen**
```sql
CREATE TABLE pricing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    price_category VARCHAR(50) NOT NULL,  -- '1' bis '9'
    garment_type VARCHAR(50) NOT NULL,    -- 'suit', 'jacket', etc.
    base_price DECIMAL(10,2) NOT NULL,
    price_per_meter DECIMAL(10,2),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(price_category, garment_type)
);

-- Beispiel-Daten
INSERT INTO pricing_rules (price_category, garment_type, base_price, description) VALUES
('9', 'suit', 2400.00, 'Premium Wool - Top Tier'),
('8', 'suit', 2100.00, 'High-end Wool'),
('7', 'suit', 1900.00, 'Premium Wool'),
-- ... weitere Kategorien
```

**Option B: Preise direkt in `fabrics` Tabelle**
```sql
ALTER TABLE fabrics
ADD COLUMN base_price_suit DECIMAL(10,2),
ADD COLUMN base_price_jacket DECIMAL(10,2),
ADD COLUMN base_price_trousers DECIMAL(10,2);
```

**Empfehlung:** Option A (pricing_rules) ist flexibler und wartbarer.

---

## 🔧 Empfohlene Preiskategorien-Mapping

Basierend auf `additional_metadata.preiskat`:

| Preiskat | Beschreibung | Anzug (2-Teil) | Sakko | Hose |
|----------|--------------|----------------|-------|------|
| 1-2 | Entry Level | 1200€ | 800€ | 400€ |
| 3-4 | Standard | 1500€ | 950€ | 500€ |
| 5-6 | Premium | 1800€ | 1150€ | 600€ |
| 7-8 | High-End | 2100€ | 1350€ | 700€ |
| 9 | Luxury | 2400€ | 1550€ | 800€ |

**Aufschläge:**
- 3-Teiler: +300€
- Smoking: +400€
- Mantel: +700€
- Monogramm: +50€
- Express (< 3 Wochen): +200€

---

## 📋 Aktionsplan

### Phase 1: Embedding-Dimensionen verifizieren 🔴

**Status:** ⏳ In Progress

**Aufgaben:**
1. ✅ Korrigiertes Inspektionsskript erstellt (`verify_embeddings.py`)
2. ⏳ User muss Skript mit korrekter `.env` ausführen
3. ⏳ Dimensionen in `rag_docs` verifizieren (sollen 384 sein)
4. ⏳ Falls Mismatch: Embedding-Modell in Code identifizieren

**Command:**
```bash
python verify_embeddings.py
```

**Erwartetes Ergebnis:**
```
✅ rag_docs.embedding: 384 Dimensionen
ℹ️  fabric_embeddings.embedding: Keine Daten vorhanden
```

---

### Phase 2: Fabric Embeddings generieren 🔴

**Status:** ⏳ Pending (abhängig von Phase 1)

**Aufgaben:**
1. Script erstellen: `scripts/generate_fabric_embeddings.py`
2. Für alle 1988 Stoffe:
   - Beschreibungen generieren (aus DB-Feldern)
   - Chunks erstellen (4 Typen)
   - Embeddings mit OpenAI API generieren
   - In `fabric_embeddings` speichern
3. Testing: RAG-Abfragen testen

**Chunking-Strategie:**
```python
# Chunk 1: Characteristics
f"{fabric.name} - {fabric.composition}, {fabric.weight}g/m², {fabric.color}, {fabric.pattern}"

# Chunk 2: Visual Description
f"Farbe: {fabric.color}, Muster: {fabric.pattern}, visuell: ..."

# Chunk 3: Usage Context
f"Kategorie: {fabric.category}, Saison: {season}, Anlass: {occasion}"

# Chunk 4: Technical
f"Pflege: {fabric.care_instructions}, Herkunft: {fabric.origin}, Lieferant: {fabric.supplier}"
```

**Kosten-Schätzung:**
- 1988 Stoffe × 4 Chunks = 7952 Embeddings
- text-embedding-3-small: $0.02 / 1M tokens
- Durchschnitt ~50 tokens/chunk = 400k tokens
- **Kosten: ~$0.008** (vernachlässigbar)

**Dauer:** ~15-30 Minuten (abhängig von API Rate Limits)

---

### Phase 3: Pricing Schema erstellen 🟡

**Status:** ⏳ Pending

**Aufgaben:**
1. Preiskategorien-Mapping definieren (siehe Tabelle oben)
2. `pricing_rules` Tabelle erstellen
3. Daten basierend auf `preiskat` importieren
4. Pricing Tool anpassen:
   - RAG Tool erweitern: `get_fabric_pricing(fabric_code, garment_type)`
   - Fallback behalten für ungültige Daten
5. Testing

**SQL Script:** `scripts/create_pricing_schema.sql`

**Alternative:**
Falls Google Drive Sync aktiviert wird und `price_book_by_tier.json` gefüllt wird, daraus importieren.

---

### Phase 4: RAG Tool Testing & Integration 🟢

**Status:** ⏳ Pending (abhängig von Phase 2 & 3)

**Aufgaben:**
1. RAG Tool für Fabric Search testen
2. Pricing Integration testen
3. End-to-End Workflow testen:
   - "Zeig mir navy blue wool für Business"
   - "Was kostet ein Anzug aus diesem Stoff?"
   - "Vergleiche diese 3 Stoffe"

---

## 📌 Prioritäten

### Kritischer Pfad:

1. **Phase 1** (15 Min) → Dimensionen verifizieren
2. **Phase 2** (30 Min) → Fabric Embeddings generieren
   👉 **BLOCKING für RAG Functionality**
3. **Phase 3** (45 Min) → Pricing Schema
4. **Phase 4** (30 Min) → Testing

**Total:** ~2 Stunden Entwicklungszeit

---

## 🚀 Nächste Schritte

### Sofort (User):
```bash
# 1. Dimensionen prüfen
python verify_embeddings.py

# 2. Output teilen
```

### Danach (Claude):
1. Basierend auf Dimensions-Check:
   - Falls 384: Fabric Embeddings Script erstellen
   - Falls anders: Embedding-Modell identifizieren & anpassen

2. Pricing Schema implementieren

3. End-to-End Testing

---

## 📚 Referenzen

- `docs/RAG_SETUP.md` - RAG Setup Guide
- `docs/CLEANUP_DONE.md` - Workflow Implementation Status
- `workflow/nodes.py:383` - Aktuelle Pricing Tool Implementierung
- `tools/rag_tool.py` - RAG Tool (bereit für Fabric Search)

---

**Status:** 🔴 Waiting for User to run `verify_embeddings.py`
