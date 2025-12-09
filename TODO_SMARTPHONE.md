# 📱 TODO SMARTPHONE - Unterwegs
**Datum**: 2025-12-08
**Für**: Entscheidungen, Ideen, Konzepte (ohne PC)

---

## ✅ Fabric-Daten: Wo sind die 2.000 Stoffe?

### 🔍 KLÄRUNG ERFORDERLICH
Die 140 Stoffe im `fabric_catalog.json` sind zu wenig!

**Du sagtest: ~2.000 Stoffe**
**Aktuell gefunden: 140 Anzug-Stoffe**

### ❓ Entscheidungen treffen:

#### 1️⃣ **Wo sind die restlichen ~1.860 Stoffe?**
- [ ] In PostgreSQL Datenbank bereits vorhanden?
- [ ] In Google Drive als separate Dateien?
- [ ] In weiteren PDF-Dateien (z.B. Hemden-PDFs)?
- [ ] In Excel/CSV-Dateien?
- [ ] In HENK2 System exportierbar?

**→ Aktion:** Prüfe wo die Stoffe liegen und notiere die Quelle

---

#### 2️⃣ **Hemden-Stoffe (72SH, 70SH, 73SH, 74SH)**
Du hast diese erwähnt - wo sind sie?

- [ ] Google Drive durchsuchen nach "72SH", "70SH", "73SH", "74SH"
- [ ] HENK2 System: Export-Funktion für Hemden-Stoffe?
- [ ] PDF-Dateien mit Hemden-Katalog?
- [ ] Excel-Listen mit Hemden-Stoffen?

**→ Aktion:** Notiere Speicherort und Format (PDF/Excel/JSON)

---

#### 3️⃣ **Datenbank-Strategie**
Alle Fabrics MÜSSEN in PostgreSQL Datenbank!

**Entscheide:**
- [ ] Sind bereits Stoffe in der DB? (→ am PC prüfen mit `scripts/inspect_db.py`)
- [ ] Sollen alle Stoffe neu importiert werden?
- [ ] Oder nur fehlende Stoffe ergänzen?
- [ ] Duplikate vermeiden: Stoff-Referenz als Unique Key?

**→ Aktion:** Entscheide Import-Strategie (komplett neu vs. inkrementell)

---

## 🎯 Google Drive Organisation

### 📂 Welche Dateien brauchst du aus Google Drive?

#### **Hemden-Stoffe** (PRIORITÄT 1)
- [ ] Dateien mit Hemden-Stoffen finden
- [ ] Format prüfen (PDF/Excel/JSON?)
- [ ] Anzahl Stoffe schätzen
- [ ] Download-Link notieren

#### **Garment-Katalog Daten** (PRIORITÄT 2)
- [ ] Beschreibungen für Anzüge (dreiteilig, zweiteilig)
- [ ] Beschreibungen für Hemden
- [ ] Beschreibungen für Hosen, Sakkos, Westen, Mäntel
- [ ] Format: Text-Dateien? Word? Google Docs?

#### **HENK2 Options** (PRIORITÄT 3)
- [ ] Alle Maßkonfektion-Optionen
- [ ] Revers, Knöpfe, Futter, Schulterpolster, etc.
- [ ] Hosenbund, Bundfalten, Aufschläge
- [ ] Westen-Optionen
- [ ] Format prüfen (Excel/JSON/Text?)

#### **Style Knowledge Base** (PRIORITÄT 4)
- [ ] Dress Codes (Business Formal, Casual, etc.)
- [ ] Farb-Kombinationen
- [ ] Style Rules
- [ ] Body Type Recommendations
- [ ] Format: Google Docs? PDF? Slides?

**→ Aktion:** Für jede Kategorie: Dateinamen und Speicherort notieren

---

## 🔐 API Keys & Credentials

### **Google Drive Zugriff**
- [ ] Hast du Google Service Account Credentials?
- [ ] Wo liegt die JSON-Datei? (für GOOGLE_APPLICATION_CREDENTIALS)
- [ ] Welche Folder ID für HENK Google Drive?

### **OpenAI API Key**
- [ ] OpenAI API Key bereit?
- [ ] Optional: Organization ID?

### **Pipedrive CRM**
- [ ] Pipedrive API Key verfügbar?
- [ ] Pipedrive Domain (z.B. "henninglutz-company")?

### **PostgreSQL Datenbank**
- [ ] Läuft die Datenbank lokal oder remote?
- [ ] Host und Port bekannt?
- [ ] Username und Password notieren
- [ ] Datenbank-Name: "henk_rag"?

**→ Aktion:** Alle Keys sicher notieren (nicht hier im Repo!)

---

## 💡 Konzeptionelle Entscheidungen

### **RAG-System Design**

#### Katalog-Chunks Strategie
Wie sollen Kataloge in RAG-Chunks aufgeteilt werden?

**Garment-Katalog:**
- [ ] Ein Chunk pro Kleidungsstück? (Anzug, Hemd, Hose...)
- [ ] Oder ein Chunk pro Kategorie?
- [ ] Chunk-Größe: ~500-1000 Tokens?

**Hemden-Stoffe:**
- [ ] Ein Chunk pro Stoff-Serie (72SH als Gruppe)?
- [ ] Oder ein Chunk pro einzelnem Stoff?
- [ ] Chunk-Größe: ~300-500 Tokens?

**Style-Katalog:**
- [ ] Ein Chunk pro Dress Code?
- [ ] Separate Chunks für Farb-Kombinationen?
- [ ] Body Type als eigene Chunks?

**→ Aktion:** Entscheide Chunking-Strategie für beste RAG-Performance

---

### **Agent-Prompts Integration**

Die 4 Prompts sind vorhanden:
1. `henk_core_prompt_optimized.txt` - Haupt-Persona
2. `henk1_prompt.txt` - HENK1 (Bedarfsermittlung)
3. `henk2_prompt_drive_style.txt` - HENK2 (Style & Stoffe)
4. `henk3_prompt_measurement.txt` - HENK3 (Vermessung)

**Entscheide:**
- [ ] Prompts direkt in Agent-Code einbauen?
- [ ] Oder dynamisch aus Dateien laden?
- [ ] Prompt-Versionierung wichtig?
- [ ] Sollen Prompts in .env konfigurierbar sein?

**→ Aktion:** Wähle Prompt-Integrations-Strategie

---

### **Embedding-Strategie**

**Modell-Wahl:**
- [ ] OpenAI `text-embedding-3-small` (384 dims) - AKTUELL
- [ ] Oder OpenAI `text-embedding-3-large` (3072 dims)?
- [ ] Oder lokales Modell (sentence-transformers)?

**Kosten-Kalkulation (OpenAI):**
- 2.000 Stoffe × 4 Chunks = 8.000 Chunks
- ~300 Tokens pro Chunk = 2.4M Tokens
- text-embedding-3-small: $0.00002 / 1K tokens
- **Geschätzt: ~$0.05** (sehr günstig!)

**→ Entscheidung:** OpenAI small (384d) reicht aus!

---

## 📊 Daten-Qualität & Validierung

### **Welche Stoffe brauchen wir wirklich?**

**Kategorien priorisieren:**
1. [ ] **Anzug-Stoffe** (Business, Formal) - KRITISCH
2. [ ] **Hemden-Stoffe** (72SH, 70SH, 73SH, 74SH) - KRITISCH
3. [ ] **Hosen-Stoffe** (separat oder Teil von Anzug?)
4. [ ] **Mantel-Stoffe** (Winter, Herbst)
5. [ ] **Westen-Stoffe** (oder aus Anzug-Stoffen?)

**→ Aktion:** Priorisiere Stoff-Kategorien nach Business-Impact

---

### **Stoff-Daten Vollständigkeit**

Für jeden Stoff brauchen wir MINIMUM:
- [ ] Referenznummer (z.B. "695.401/18")
- [ ] Lieferant (z.B. "Vitale Barberis")
- [ ] Zusammensetzung (z.B. "100% Virgin Wool")
- [ ] Gewicht (z.B. "250 g/m²")
- [ ] CAT-Kategorie (z.B. "CAT 5")
- [ ] Preis-Tier (Einstieg/Premium/Luxus)

**NICE-TO-HAVE:**
- [ ] Farbe
- [ ] Muster
- [ ] Saison (Sommer/Winter/Ganzjährig)
- [ ] Verfügbarkeit

**→ Aktion:** Prüfe ob alle Stoffe diese Felder haben

---

## 🎨 Style-System Design

### **Wie detailliert sollen Style-Empfehlungen sein?**

**Option A: Minimalistisch**
- Nur grundlegende Dress Codes
- Einfache Farb-Kombinationen
- Basis Body Types

**Option B: Detailliert**
- Alle Dress Codes mit Beispielen
- Umfangreiche Farb-Palette
- 6+ Body Types mit spezifischen Tipps
- Pattern Mixing Rules
- Seasonal Guidelines

**→ Entscheidung:** Wähle Detailgrad für MVP

---

## 🔄 Workflow & Prozesse

### **Google Drive Sync**

**Wie oft synchronisieren?**
- [ ] Manuell (auf Anfrage)?
- [ ] Täglich automatisch?
- [ ] Wöchentlich?
- [ ] Bei Änderungen (Webhook)?

**Was synchronisieren?**
- [ ] Nur neue Dateien?
- [ ] Alle Dateien neu laden?
- [ ] Nur geänderte Dateien?

**→ Entscheidung:** Definiere Sync-Frequenz

---

## 📱 Integration & APIs

### **n8n Webhook Integration**

In `henk1_prompt.txt` steht:
```
webhook.post (Lead/Termin an n8n senden)
```

**Fragen:**
- [ ] Läuft n8n bereits?
- [ ] Webhook-URL verfügbar?
- [ ] Welche Daten sollen gesendet werden?
- [ ] Format: JSON Schema definieren?

**→ Aktion:** Notiere n8n Webhook-URL falls vorhanden

---

### **SAIA 3D Measurement**

Für LASERHENK (HENK3) geplant:
- [ ] SAIA API verfügbar?
- [ ] Test-Account vorhanden?
- [ ] Integration Priorität? (später?)

**→ Entscheidung:** SAIA für MVP oder später?

---

## 🧪 Test-Strategie

### **Was muss getestet werden?**

**Datenbank:**
- [ ] Alle 2.000 Stoffe importiert?
- [ ] Embeddings korrekt generiert?
- [ ] RAG-Queries funktionieren?

**Agents:**
- [ ] HENK1 → HENK2 Handoff funktioniert?
- [ ] HENK2 findet passende Stoffe?
- [ ] HENK3 verarbeitet Messdaten?

**Prompts:**
- [ ] Tonalität stimmt? (charmant, locker, stilvoll)
- [ ] Keine CAT-Codes in Antworten?
- [ ] Termin-JSON korrekt?

**→ Aktion:** Definiere Test-Szenarien

---

## 📝 Dokumentation

### **Was muss dokumentiert werden?**

- [ ] Setup-Anleitung für neues Team-Mitglied
- [ ] Katalog-Struktur erklärt
- [ ] Embedding-Prozess dokumentiert
- [ ] Agent-Workflow mit Diagramm
- [ ] RAG-Query Beispiele

**→ Entscheidung:** Dokumentations-Umfang für MVP

---

## 🎯 MVP Definition

### **Was ist das Minimum Viable Product?**

**Phase 1 (Diese Woche):**
- [ ] Alle Stoffe in Datenbank
- [ ] Fabric Embeddings funktionieren
- [ ] RAG findet passende Stoffe
- [ ] HENK1 → HENK2 Workflow läuft

**Phase 2 (Nächste Woche):**
- [ ] Alle Kataloge befüllt
- [ ] Style-Empfehlungen funktionieren
- [ ] HENK3 Integration
- [ ] DALLE Moodboards

**Phase 3 (Später):**
- [ ] SAIA Integration
- [ ] n8n Webhooks
- [ ] Pipedrive CRM
- [ ] Production-Ready

**→ Entscheidung:** Was muss in Phase 1?

---

## 🚀 Nächste Schritte (am PC dann umsetzen)

**Nach dieser Liste:**
1. ✅ Alle Entscheidungen getroffen
2. ✅ Datenquellen identifiziert
3. ✅ API Keys gesammelt
4. ✅ Strategie festgelegt

**Dann am PC:**
→ Siehe `TODO_RECHNER.md` für technische Umsetzung

---

**Version**: 1.0
**Datum**: 2025-12-08
**Nächstes Update**: Nach Datenquellen-Recherche
