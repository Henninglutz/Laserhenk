# Material-Filter Empfehlung

## ✅ AKTUELL IMPLEMENTIERT (Korrigiert)

**Datei:** `workflow/nodes.py:680-690`

```python
# FILTER: Nur Polyurethan ausschließen (Outerwear, nicht für Anzüge)
# Polyester und Elastan sind OK für Anzüge (Stretch, Pflegeleichtigkeit)
recommendations = [
    rec for rec in recommendations
    if "polyurethan" not in (rec.fabric.composition or "").lower()
]
```

**Was gefiltert wird:**
- ❌ Polyurethan (Outerwear-Material)

**Was NICHT gefiltert wird (OK für Anzüge):**
- ✅ Polyester (z.B. 98% Wolle, 2% Polyester für Pflegeleichtigkeit)
- ✅ Elasthan (z.B. für Stretch-Anzüge)
- ✅ Nylon (kann in Futterstoff verwendet werden)

---

## 🎯 BESSERE LÖSUNG: DB-Kategorien nutzen

### **Problem mit Material-Filtern:**
- Unflexibel: Jedes neue Material muss hart-codiert werden
- Fehleranfällig: Was ist mit "Polyurethane", "PU", "Pu-beschichtet"?
- Business-Logik im Code statt in Daten

### **Lösung: `category` Feld nutzen**

**Fabric Model hat bereits:**
```python
# models/fabric.py:80-82
category: Optional[str] = Field(
    None, description="Fabric category (e.g., 'suiting', 'casual')"
)
```

### **Implementierung:**

#### **1. Datenbank-Kategorien pflegen:**
```sql
-- In Fabric-Catalog JSON oder direkt in DB:
UPDATE fabrics SET category = 'suiting' WHERE composition LIKE '%Wolle%';
UPDATE fabrics SET category = 'outerwear' WHERE composition LIKE '%Polyurethan%';
UPDATE fabrics SET category = 'casual' WHERE composition LIKE '%Baumwolle%';
```

#### **2. Filter in RAG-Query:**
```python
# tools/rag_tool.py:search_fabrics()
async def search_fabrics(
    self,
    criteria: FabricSearchCriteria,
    garment_type: str = "suit"  # NEU!
):
    # SQL WHERE Clause
    query = "SELECT * FROM fabrics WHERE ..."

    # Filter by category based on garment type
    if garment_type == "suit":
        query += " AND (category = 'suiting' OR category IS NULL)"
    elif garment_type == "jacket":
        query += " AND category IN ('suiting', 'casual', 'outerwear')"

    # Execute query...
```

#### **3. Oder Post-Filter (einfacher):**
```python
# workflow/nodes.py:678
recommendations = await rag.search_fabrics(criteria)

# Filter by category
ALLOWED_CATEGORIES_FOR_SUITS = ["suiting", "business", "formal", None]
recommendations = [
    rec for rec in recommendations
    if rec.fabric.category in ALLOWED_CATEGORIES_FOR_SUITS
]
```

---

## 📊 VORTEILE DB-KATEGORIEN:

| Aspekt | Material-Filter (JETZT) | Category-Filter (BESSER) |
|--------|-------------------------|--------------------------|
| **Flexibilität** | ❌ Neue Materialien = Code-Änderung | ✅ Neue Stoffe = Daten-Änderung |
| **Wartbarkeit** | ❌ Hardcoded Business-Logic | ✅ Business-Logic in Daten |
| **Erweiterbarkeit** | ❌ Schwierig (z.B. Hemden, Hosen) | ✅ Einfach (neue Kategorien) |
| **Genauigkeit** | ⚠️ Material-basiert (ungenau) | ✅ Experten-kuratiert |
| **Performance** | ✅ In-Memory Filter | ✅ DB-Index möglich |

---

## 🚀 MIGRATIONS-PLAN

### **Phase 1: Daten vorbereiten (1-2 Tage)**
1. Fabric Catalog durchgehen
2. Categories definieren:
   - `suiting` - Anzugstoffe
   - `shirting` - Hemdenstoffe
   - `outerwear` - Jacken, Mäntel
   - `casual` - Freizeitkleidung
   - `lining` - Futterstoff
3. JSON/DB updaten

### **Phase 2: Code anpassen (1 Tag)**
```python
# FabricSearchCriteria erweitern
class FabricSearchCriteria(BaseModel):
    colors: list[str] = []
    patterns: list[str] = []
    garment_type: str = "suit"  # NEU!
    allowed_categories: list[str] = ["suiting"]  # NEU!
```

### **Phase 3: Übergangsphase (1 Woche)**
- Beide Filter parallel laufen lassen
- Monitoren ob Category-Filter funktioniert
- Wenn alles OK → Material-Filter entfernen

### **Phase 4: Erweitern**
- Hemden: `garment_type="shirt"` → `category="shirting"`
- Hosen: `garment_type="trousers"` → `category IN ("suiting", "casual")`
- Jacken: `garment_type="jacket"` → `category="outerwear"`

---

## 💡 SOFORT-EMPFEHLUNG

**Für JETZT (Polyurethan-Filter):**
✅ Gut genug, deployed

**Für NÄCHSTE WOCHE:**
1. Fabric Catalog durchsehen
2. Categories manuell setzen (Top 50 Stoffe)
3. Category-Filter implementieren
4. Testen

**Für SPÄTER:**
- ML-basierte Auto-Kategorisierung
- Multi-Use Fabrics (sowohl Anzug als auch Casual)
- User-Feedback Loop (Stoff falsch? → Re-kategorisieren)

---

**Erstellt:** 2025-12-16
**Status:** Polyurethan-Filter aktiv, Category-System geplant
