# Formens B2B Scraping & Import Workflow

Kompletter Workflow zum Scrapen aller Stoffe von Formens B2B und Import in die PostgreSQL-Datenbank für RAG.

## 🎯 Übersicht

```
1. Scrapen  →  2. Import  →  3. Embeddings  →  4. RAG bereit!
```

---

## 📋 Voraussetzungen

```bash
# Python dependencies installieren
pip install requests beautifulsoup4 asyncpg

# Umgebungsvariablen setzen
export FORMENS_EMAIL="deine@email.de"
export FORMENS_PASSWORD="deinPasswort"
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
```

---

## 1️⃣ Schritt 1: Stoffe scrapen

Das Scraping-Script holt alle Stoffe von `https://b2b2.formens.ro/stocktisue` und speichert sie als JSON mit Bildern.

### Mit Login (empfohlen):

```bash
python scripts/scrape_formens_b2b.py \
  --email "$FORMENS_EMAIL" \
  --password "$FORMENS_PASSWORD" \
  --output-dir storage/fabrics
```

### Mit Browser-Cookie (Alternative):

```bash
# Cookie aus Browser kopieren (z.B. aus DevTools)
python scripts/scrape_formens_b2b.py \
  --cookie "PHPSESSID=abc123..." \
  --output-dir storage/fabrics
```

### Wichtige Parameter:

- `--max-pages`: Standard ist 999, stoppt automatisch wenn keine neuen Produkte gefunden werden
- `--output-dir`: Wo JSON und Bilder gespeichert werden (Standard: `storage/fabrics`)
- `--no-images`: Bilder nicht herunterladen (nur Metadaten)
- `--sleep`: Wartezeit zwischen Requests in Sekunden (Standard: 0.7s)

### Output:

```
storage/fabrics/
├── formens_fabrics.json    # Alle Stoffe als JSON
└── images/                  # Heruntergeladene Stoff-Bilder
    ├── FABRIC001.jpg
    ├── FABRIC002.jpg
    └── ...
```

### Was wird gescraped?

Für jeden Stoff:
- ✅ Fabric Code (eindeutige ID)
- ✅ Name
- ✅ Komposition (Material)
- ✅ Gewicht
- ✅ Herkunft
- ✅ Preiskategorie
- ✅ Beschreibung
- ✅ Hauptbild
- ✅ URL zur Detailseite
- ✅ Extra-Felder (Farbe, Saison, etc.)

---

## 2️⃣ Schritt 2: Import in PostgreSQL

Nach dem Scraping müssen die Daten in die Datenbank importiert werden:

```bash
python scripts/import_formens_to_db.py
```

### Was passiert beim Import?

1. **Lädt** `storage/fabrics/formens_fabrics.json`
2. **Prüft** für jeden Stoff, ob er bereits existiert (nach `fabric_code` oder URL)
3. **Update** existierende Stoffe mit neuen Daten
4. **Insert** neue Stoffe in die `fabrics` Tabelle
5. **Speichert** alle Metadaten im `additional_metadata` JSON-Feld

### Import-Statistiken:

```
✓ Inserted: 1988 new fabrics
✓ Updated: 0 existing fabrics
📊 Final database state:
   Total fabrics: 2128
   Formens fabrics: 1988
```

---

## 3️⃣ Schritt 3: Embeddings generieren

Damit die Stoffe per RAG durchsuchbar sind, müssen Embeddings generiert werden:

```bash
python scripts/generate_fabric_embeddings.py
```

Dies erstellt semantische Embeddings für:
- Fabric Code
- Name
- Komposition
- Beschreibung
- Alle Metadaten

### Embeddings verifizieren:

```bash
python scripts/verify_embeddings.py
```

---

## 4️⃣ Schritt 4: RAG testen

Jetzt kannst du die Stoffe im RAG abfragen:

```python
# Im HENK1 Chat oder direkt über die RAG API:
"Zeig mir alle Stoffe von Formens"
"Welche Stoffe haben 100% Wolle?"
"Finde mir einen leichten Sommerstoff"
"Zeig mir Stoffe in Preiskategorie 3"
```

---

## 🔄 Kompletter Workflow (Copy-Paste)

```bash
# 1. Scrapen
python scripts/scrape_formens_b2b.py \
  --email "$FORMENS_EMAIL" \
  --password "$FORMENS_PASSWORD" \
  --output-dir storage/fabrics

# 2. Import
python scripts/import_formens_to_db.py

# 3. Embeddings
python scripts/generate_fabric_embeddings.py

# 4. Test
python scripts/verify_embeddings.py
```

---

## 🛠️ Troubleshooting

### Problem: Login schlägt fehl

**Lösung 1**: Cookie verwenden statt Login
```bash
# Im Browser: DevTools → Application → Cookies → PHPSESSID kopieren
python scripts/scrape_formens_b2b.py --cookie "PHPSESSID=xyz..."
```

**Lösung 2**: `--allow-anonymous` verwenden (wenn möglich)
```bash
python scripts/scrape_formens_b2b.py --allow-anonymous
```

### Problem: Keine Stoffe gefunden

**Ursache**: Falsche URL oder nicht eingeloggt

**Lösung**: Script zeigt automatisch verwendete URLs an:
```
🔍 Loading homepage to find login form...
🔍 Following login link: https://...
🌐 Listing page 1: https://b2b2.formens.ro/stocktisue?page=1
```

Prüfe diese URLs im Browser.

### Problem: Import schlägt fehl

**Ursache**: Datenbank nicht erreichbar oder falsches Schema

**Lösung 1**: Verbindung prüfen
```bash
echo $DATABASE_URL
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM fabrics;"
```

**Lösung 2**: Schema prüfen
```sql
-- fabrics Tabelle muss existieren mit:
-- id, fabric_code, name, composition, weight, origin,
-- description, supplier, category, additional_metadata
```

### Problem: Duplikate in der Datenbank

Das Import-Script erkennt Duplikate automatisch und updated sie.

**Manuelle Prüfung**:
```sql
SELECT fabric_code, COUNT(*)
FROM fabrics
GROUP BY fabric_code
HAVING COUNT(*) > 1;
```

---

## 📊 Datenbank-Schema

Die `fabrics` Tabelle enthält:

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | UUID | Primärschlüssel |
| `fabric_code` | VARCHAR | Eindeutige Stoff-ID (z.B. "FABRIC001") |
| `name` | VARCHAR | Stoff-Name |
| `composition` | TEXT | Material-Zusammensetzung |
| `weight` | VARCHAR | Gewicht (z.B. "250 g/m²") |
| `origin` | VARCHAR | Herkunftsland |
| `description` | TEXT | Beschreibung |
| `supplier` | VARCHAR | Lieferant (hier: "Formens") |
| `category` | VARCHAR | Preiskategorie |
| `additional_metadata` | JSONB | Alle Extra-Felder (Bild-URL, Farbe, etc.) |
| `created_at` | TIMESTAMP | Erstellungsdatum |
| `updated_at` | TIMESTAMP | Letzte Änderung |

---

## 🔍 Nützliche SQL-Queries

```sql
-- Alle Formens-Stoffe anzeigen
SELECT fabric_code, name, composition, weight, category
FROM fabrics
WHERE supplier = 'Formens'
ORDER BY fabric_code;

-- Stoffe nach Komposition suchen
SELECT fabric_code, name, composition
FROM fabrics
WHERE composition ILIKE '%wool%'
  AND supplier = 'Formens';

-- Preiskategorien zählen
SELECT category, COUNT(*)
FROM fabrics
WHERE supplier = 'Formens'
GROUP BY category
ORDER BY category;

-- Stoffe mit Bildern
SELECT fabric_code, name, additional_metadata->>'image_url' as image
FROM fabrics
WHERE supplier = 'Formens'
  AND additional_metadata->>'image_url' IS NOT NULL;
```

---

## 🎯 Best Practices

1. **Regelmäßig scrapen**: Führe das Scraping regelmäßig aus (z.B. wöchentlich), um neue Stoffe zu erfassen
2. **Backup vor Import**: Erstelle ein Datenbank-Backup vor größeren Imports
3. **Embeddings nach Import**: Generiere immer neue Embeddings nach dem Import
4. **Rate Limiting**: Nutze `--sleep 1` oder höher bei Problemen mit Rate Limiting
5. **Logs prüfen**: Alle Scripts zeigen detaillierte Logs - bei Problemen durchlesen

---

## ✅ Checkliste

- [ ] Credentials gesetzt (`FORMENS_EMAIL`, `FORMENS_PASSWORD`)
- [ ] Database URL gesetzt (`DATABASE_URL`)
- [ ] Scraping erfolgreich (JSON-Datei erstellt)
- [ ] Import erfolgreich (Stoffe in DB)
- [ ] Embeddings generiert
- [ ] RAG-Queries funktionieren

---

## 📝 Notizen

- Die Website `b2b2.formens.ro` hostet **ca. 1988 Stoffe** (Stand: Dez 2024)
- Alle Produkte sind auf **einer Seite**: `/stocktisue`
- Das Scraping dauert ca. **30-40 Minuten** (mit Images)
- Der Import dauert ca. **2-3 Minuten**
- Embeddings dauern ca. **5-10 Minuten**

---

Viel Erfolg! 🚀
