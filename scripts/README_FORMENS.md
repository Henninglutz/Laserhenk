# Formens B2B Scraping - Quick Start

## 🚀 Schnellstart (Copy-Paste)

```bash
# Scrape ALLE Stoffe (~1988 Produkte, dauert 30-40 Minuten):
python scripts/scrape_formens_b2b.py \
  --username "Henning" \
  --password "Dolcev1ta1nCatan1a!" \
  --output-dir storage/fabrics
```

**Das war's!** Das Script:
- ✅ Loggt sich automatisch ein
- ✅ Findet die richtige URL (`/stocktisue`)
- ✅ Scrapt ALLE Stoffe (stoppt automatisch)
- ✅ Speichert JSON + Bilder in `storage/fabrics/`

---

## 📋 Nach dem Scraping

### Import in PostgreSQL:

```bash
python scripts/import_formens_to_db.py
```

### Embeddings generieren:

```bash
python scripts/generate_fabric_embeddings.py
```

---

## 🔧 Alternative: Cookie verwenden

Wenn Login nicht funktioniert:

```bash
# 1. Öffne https://b2b2.formens.ro im Browser
# 2. Logge dich ein
# 3. Öffne DevTools (F12) → Application → Cookies
# 4. Kopiere PHPSESSID-Cookie

python scripts/scrape_formens_b2b.py \
  --cookie "PHPSESSID=abc123..." \
  --output-dir storage/fabrics
```

**Hilfe beim Cookie-Extrahieren:**

```bash
python scripts/get_formens_cookie.py --interactive
```

---

## 🎯 Automatischer Workflow

Das Quick-Start-Script macht alles auf einmal:

```bash
# 1. Credentials setzen
export FORMENS_USERNAME="Henning"
export FORMENS_PASSWORD="Dolcev1ta1nCatan1a!"
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# 2. Alles ausführen
./scripts/formens_quickstart.sh
```

---

## ❓ Probleme?

### Problem: "Login ist erforderlich"

**Lösung**: Credentials direkt übergeben (siehe oben) statt Umgebungsvariablen

### Problem: "Login failed"

**Lösung 1**: Cookie verwenden (siehe oben)

**Lösung 2**: Credentials prüfen
```bash
echo "Username: Henning"
echo "Password: Dolcev1ta1nCatan1a!"
```

### Problem: "Received a login page instead of listings"

**Lösung**: Login ist fehlgeschlagen, Cookie verwenden

---

## 📚 Vollständige Dokumentation

Siehe: [`docs/FORMENS_WORKFLOW.md`](../docs/FORMENS_WORKFLOW.md)

Dort findest du:
- Detaillierte Erklärungen
- Alle Parameter und Optionen
- SQL-Queries für die Datenbank
- Best Practices
- Ausführliches Troubleshooting

---

## ✅ Checkliste

- [ ] Scraping erfolgreich (JSON-Datei in `storage/fabrics/` erstellt)
- [ ] Import zu PostgreSQL (mit `import_formens_to_db.py`)
- [ ] Embeddings generiert (mit `generate_fabric_embeddings.py`)
- [ ] RAG funktioniert ("Zeig mir Stoffe von Formens")

---

**Fertig!** 🎉
