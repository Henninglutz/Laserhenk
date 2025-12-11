# 📦 Fabric Data Setup - LASERHENK

Anleitung zum Einrichten der Fabric-Daten vom Scraper.

---

## ⚠️ WICHTIG: data/ Ordner ist in .gitignore

Der `data/` Ordner wird **NICHT ins Git-Repository committed**!

Die Fabric-Daten (JSON + Bilder) müssen vom **henk.bettercallhenk.de Scraper** geholt werden.

---

## 📁 Benötigte Struktur

```
data/
├── fabrics/
│   ├── fabrics2.json          # 2256+ Stoffe vom Scraper (ERFORDERLICH)
│   └── images/                # Fabric-Bilder für DALLE (ERFORDERLICH)
│       ├── 70SH2109.jpg
│       ├── 70SH2110.jpg
│       └── ... (~2256 Bilder)
```

---

## 🔗 Datenquelle

**Repository:** https://github.com/Henninglutz/henk.bettercallhenk.de (Scraper)

**Output-Struktur im Scraper:**
```
henk.bettercallhenk.de/
└── output/
    ├── fabrics2.json      # → Kopieren nach: data/fabrics/fabrics2.json
    └── images/            # → Kopieren nach: data/fabrics/images/
        ├── 70SH2109.jpg
        └── ...
```

---

## 🚀 Setup-Optionen

### Option 1: Automatisches Setup-Script ⭐

```bash
# Script ausführen
./scripts/setup_fabric_data.sh

# Script zeigt Status und gibt Anweisungen
```

Das Script:
- ✓ Erstellt benötigte Ordner-Struktur
- ✓ Prüft, ob fabrics2.json vorhanden ist
- ✓ Zählt vorhandene Bilder
- ✓ Gibt konkrete Anweisungen, falls Daten fehlen

---

### Option 2: Manuelle Einrichtung

#### Schritt 1: Scraper-Repository klonen

```bash
cd /tmp
git clone https://github.com/Henninglutz/henk.bettercallhenk.de.git
cd henk.bettercallhenk.de
```

Falls privates Repository:
```bash
# Mit GitHub Authentication
gh auth login
git clone https://github.com/Henninglutz/henk.bettercallhenk.de.git
```

#### Schritt 2: Scraper ausführen (falls nötig)

```bash
# Im Scraper-Repository
# (Details siehe Scraper-README)
npm install
npm run scrape
```

Output wird in `output/` Ordner generiert.

#### Schritt 3: Daten nach Laserhenk kopieren

```bash
# Zurück ins Laserhenk Repository
cd /home/user/Laserhenk

# Ordner-Struktur erstellen
mkdir -p data/fabrics/images

# fabrics2.json kopieren
cp /tmp/henk.bettercallhenk.de/output/fabrics2.json ./data/fabrics/

# Bilder kopieren
cp -r /tmp/henk.bettercallhenk.de/output/images/* ./data/fabrics/images/
```

#### Schritt 4: Verifizieren

```bash
# Anzahl Fabrics prüfen
jq 'length' data/fabrics/fabrics2.json
# Erwartet: 2256

# Anzahl Bilder prüfen
ls -1 data/fabrics/images/ | wc -l
# Erwartet: ~2256

# Beispiel-Fabric anzeigen
jq '.[0]' data/fabrics/fabrics2.json
```

**Erwartetes Format:**
```json
{
  "fabric_code": "70SH2109",
  "name": "Hochwertige Wollmischung",
  "composition": "100% Wool",
  "weight": "250g/m²",
  "color": "Navy Blue",
  "pattern": "Solid",
  "category": "Suiting",
  "supplier": "Scabal",
  "stock_status": "In Stock",
  "price_category": "5"
}
```

---

### Option 3: Daten vom Server holen

Falls Scraper-Daten auf einem Server liegen:

```bash
# SCP für fabrics2.json
scp user@server:/pfad/zu/fabrics2.json ./data/fabrics/

# RSYNC für Bilder (effizienter für viele Dateien)
rsync -avz --progress user@server:/pfad/zu/images/ ./data/fabrics/images/

# Beispiel mit spezifischem Host
rsync -avz --progress henk@bettercallhenk.de:/var/www/scraper/output/images/ ./data/fabrics/images/
```

---

## 📥 Import in PostgreSQL Datenbank

Nach erfolgreichem Setup der Daten:

```bash
# 1. Dependencies installieren (falls noch nicht geschehen)
pip install asyncpg sqlalchemy openai python-dotenv

# 2. .env konfigurieren
cp .env.example .env
# → DATABASE_URL und OPENAI_API_KEY setzen

# 3. Fabric-Daten importieren
python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json

# Output:
# ✓ Loaded 2256 fabrics from JSON
# ✓ Updated: X existing fabrics
# ✓ Inserted: Y new fabrics
# Total fabrics: 2256
# With metadata: 2256 (100.0%)

# 4. Embeddings generieren
python scripts/generate_fabric_embeddings.py

# Output:
# Fabrics Processed: 2256
# Chunks Created: ~9024
# Embeddings Generated: ~9024
# Estimated Cost: ~$0.02

# 5. Verifizieren
python scripts/update_fabric_metadata.py --check
```

---

## 📊 Erwartete Datenbank-State nach Import

| Tabelle | Vor Import | Nach Import | Nach Embeddings |
|---------|-----------|-------------|-----------------|
| `fabrics` | 1988 (NULL Metadata) | 2256 (vollständig) | 2256 |
| `fabric_embeddings` | 43M (alte) | 43M (alte) | ~9024 (neu) |

---

## ❓ Troubleshooting

### Problem: "fabrics2.json not found"

**Lösung:**
```bash
# Prüfe, ob Datei existiert
ls -lh data/fabrics/fabrics2.json

# Falls nicht: Setup-Script ausführen
./scripts/setup_fabric_data.sh

# Oder manuell vom Scraper kopieren (siehe oben)
```

---

### Problem: "No images in data/fabrics/images/"

**Lösung:**
```bash
# Prüfe Anzahl
ls data/fabrics/images/ | wc -l

# Falls leer: Bilder vom Scraper kopieren
cp -r /pfad/zum/scraper/output/images/* ./data/fabrics/images/

# Oder mit rsync
rsync -avz user@server:/pfad/zu/images/ ./data/fabrics/images/
```

**Warum wichtig?**
- Bilder werden für DALLE-Integration benötigt
- HENK3 (LaserHENK) generiert Anzug-Visualisierungen basierend auf Fabric-Bildern

---

### Problem: "Scraper-Repository nicht gefunden"

**Repository-URL:** https://github.com/Henninglutz/henk.bettercallhenk.de

Falls privat:
```bash
# GitHub CLI verwenden
gh auth login
gh repo clone Henninglutz/henk.bettercallhenk.de

# Oder SSH
git clone git@github.com:Henninglutz/henk.bettercallhenk.de.git
```

Falls Repository nicht existiert:
- Kontaktiere Repository-Owner
- Scraper muss zuerst erstellt/ausgeführt werden

---

### Problem: "Weight parsing error: '250g/m²'"

✅ **FIXED** in `import_scraped_fabrics.py`

Falls Error trotzdem auftritt:
```bash
# Neueste Version holen
git pull origin claude/fix-supervisor-rag-workflow-01CDqqrRThMLyCg3xjByUwxe

# Script erneut ausführen
python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json
```

---

### Problem: "Database connection failed"

**Lösung:**
```bash
# Prüfe .env
cat .env | grep DATABASE_URL

# Format sollte sein:
# DATABASE_URL=postgresql://user:password@localhost:5432/henk_rag

# PostgreSQL Status prüfen
systemctl status postgresql

# Oder mit Docker
docker ps | grep postgres
```

---

## 🔒 Sicherheit & Best Practices

**WICHTIG:**

1. **data/ ist in .gitignore** → Keine Daten ins Git committen!
2. **Bilder können groß sein** → Mehrere GB, nicht ins Repository
3. **Sensitive Credentials** → In `.env` (auch in .gitignore)
4. **Scraper-Output** → Regelmäßig updaten für aktuelle Fabric-Daten

---

## 🔄 Daten aktualisieren

Wenn neue Fabrics vom Scraper kommen:

```bash
# 1. Scraper erneut ausführen
cd /tmp/henk.bettercallhenk.de
npm run scrape

# 2. Neue Daten kopieren
cp output/fabrics2.json /home/user/Laserhenk/data/fabrics/
cp -r output/images/* /home/user/Laserhenk/data/fabrics/images/

# 3. Datenbank aktualisieren
cd /home/user/Laserhenk
python scripts/import_scraped_fabrics.py --source data/fabrics/fabrics2.json

# 4. Embeddings neu generieren
python scripts/generate_fabric_embeddings.py
```

---

## 📚 Related Documentation

- `scripts/README.md` - Alle verfügbaren Scripts
- `docs/DATABASE_ANALYSIS.md` - Datenbank-Schema
- `docs/RAG_SETUP.md` - RAG Integration Guide
- `.env.example` - Environment Configuration

---

**Setup-Script:** `./scripts/setup_fabric_data.sh`

**Status:** 🟡 Daten müssen vom Scraper geholt werden
