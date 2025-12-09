# TODO - Laserhenk Development Plan
**Datum**: 2025-12-08
**Status**: In Progress

---

## 🎯 Heute: Kataloge, Embeddings & RAG-System

### 1. Kataloge vervollständigen

#### 1.1 Garment-Katalog
- **Datei**: `drive_mirror/henk/garments/garment_catalog.json`
- **Status**: ❌ Leer
- **Benötigt**:
  - Beschreibungen für Anzüge (dreiteilig, zweiteilig)
  - Beschreibungen für Hemden
  - Beschreibungen für Hosen
  - Beschreibungen für Sakkos, Westen, Mäntel
  - **Quelle**: Google Drive und drive_mirror Unterordner checken
- **Aktion**: RAG-Chunks generieren nach Befüllung

#### 1.2 Shirt-Katalog
- **Datei**: `drive_mirror/henk/shirts/shirt_catalog.json`
- **Status**: ❌ Leer
- **Benötigt**:
  - Hemd-Optionen und Konfigurationen
  - **Hemden-Stoffe sortieren**: 72SH..., 70SH..., 73SH..., 74SH... Referenzen
  - Stoffbeschreibungen für Hemden
  - **Quelle**: Google Drive checken (nicht im fabric_catalog.json vorhanden)
- **Aktion**: RAG-Chunks generieren nach Befüllung

#### 1.3 Options-Katalog HENK2
- **Datei**: `drive_mirror/henk/options/henk2_options_catalog.json`
- **Status**: ❌ Leer
- **Benötigt**:
  - Alle Maßkonfektion-Optionen (Revers, Futter, Knöpfe, etc.)
  - Detaillierte Beschreibungen
  - **Quelle**: HENK2 System und Google Drive
- **Aktion**: RAG-Chunks generieren nach Befüllung

#### 1.4 Style-Katalog
- **Datei**: `drive_mirror/henk/knowledge/style_catalog.json`
- **Status**: ❌ Leer
- **Benötigt**:
  - Style-Richtlinien und Empfehlungen
  - Business vs. Casual vs. Formal
  - Kombinationsregeln
  - **Quelle**: Google Drive Knowledge Base
- **Aktion**: RAG-Chunks generieren nach Befüllung

---

### 2. Fabric-Katalog & Embeddings

#### 2.1 Fabric-Katalog Status
- **Datei**: `drive_mirror/henk/fabrics/fabric_catalog.json`
- **Status**: ✅ Vorhanden (10089 Zeilen, 140 Stoffe)
- **Inhalt**: Anzug-Stoffe (CAT 5, 7, 9) mit Preisen
- **Problem**: ❌ Keine Hemden-Stoffe (72SH, 70SH, 73SH, 74SH)

#### 2.2 Hemden-Stoffe finden und sortieren
- [ ] Google Drive nach Hemden-Stoffen durchsuchen
- [ ] Stoffe mit Prefix 72SH, 70SH, 73SH, 74SH identifizieren
- [ ] In shirt_catalog.json sortieren
- [ ] Preise und CAT-Kategorien zuordnen

#### 2.3 Fabric Embeddings generieren
- [ ] Script ausführen: `python scripts/generate_fabric_embeddings.py`
- [ ] Embeddings in PostgreSQL speichern
- [ ] Embedding-Dimensionen prüfen: `python scripts/verify_embeddings.py`

---

### 3. RAG-System validieren

#### 3.1 Embedding-System
- [ ] Embedding-Dimensionen prüfen (384 für MiniLM)
- [ ] Test: `python scripts/verify_embeddings.py`
- [ ] Sicherstellen: pgvector Extension aktiviert

#### 3.2 RAG-Queries testen
- [ ] RAG-Queries für Fabrics testen
- [ ] Query: "Zeige mir Premium Anzug-Stoffe"
- [ ] Query: "Welche Hemden-Stoffe gibt es?"
- [ ] Performance messen

---

### 4. Vollständige Agent-Interaktion

#### 4.1 Fehlende Daten identifizieren
- [ ] HENK1: Welche Daten fehlen für Bedarfsermittlung?
- [ ] Design HENK: Welche Kataloge werden benötigt?
- [ ] LASERHENK: Ist SAIA-Integration vorbereitet?

#### 4.2 Agent-Tests schreiben
- [ ] Test: HENK1 → Design HENK Handoff
- [ ] Test: Design HENK → LASERHENK Handoff
- [ ] Test: CRM Lead Creation

---

### 5. Code-Qualität & Dokumentation

#### 5.1 Code-Formatierung
- [ ] `black . --check` ausführen
- [ ] `ruff check .` ausführen
- [ ] Fehler beheben falls vorhanden

#### 5.2 Tests aktualisieren
- [ ] `tests/test_workflow.py` erweitern
- [ ] Test für jeden Agent
- [ ] Integration-Tests

#### 5.3 Dokumentation
- [ ] README.md aktualisieren (neue Katalog-Struktur)
- [ ] API-Dokumentation erstellen
- [ ] Workflow-Diagramm aktualisieren

---

### 6. Features & Optimierung

#### 6.1 Google Drive Sync
- [ ] Drive Mirror Sync optimieren
- [ ] Automatisches Download fehlender Kataloge
- [ ] Credentials überprüfen

#### 6.2 Performance
- [ ] RAG-Tool Performance testen
- [ ] Database Connection Pool optimieren
- [ ] Caching für häufige Queries

---

## 📋 Prioritäten

### Heute (High Priority)
1. ✅ .env aktualisieren und Secrets vorbereiten
2. 🔄 Kataloge prüfen und fehlende Daten dokumentieren
3. Hemden-Stoffe finden und sortieren
4. Fabric-Embeddings generieren
5. RAG-System validieren

### Diese Woche (Medium Priority)
- Agent-Tests erweitern
- Dokumentation vervollständigen
- Code-Formatierung & Qualität

### Nächste Woche (Low Priority)
- Google Drive Sync automatisieren
- Performance-Optimierung
- SAIA Integration vorbereiten

---

## 🔍 Fehlende Daten (zu ergänzen)

### Aus Google Drive benötigt:
- [ ] Garment-Katalog Daten (Anzug, Hemd, Hose Beschreibungen)
- [ ] Shirt-Katalog mit Hemden-Stoffen (72SH, 70SH, 73SH, 74SH)
- [ ] Options-Katalog HENK2 (alle Maßkonfektion-Optionen)
- [ ] Style-Katalog (Richtlinien und Empfehlungen)
- [ ] HENK Prompts und Templates

### Zu überprüfen:
- [ ] drive_mirror/henk/ alle Unterordner durchsuchen
- [ ] Google Drive Hauptordner checken
- [ ] HENK2 System exportieren

---

## ✅ Heute erledigt
- [x] Projekt-Struktur analysiert
- [x] Leere Dateien identifiziert (.gitkeep Dateien)
- [x] .env.example aktualisiert mit vollständigem Template
- [x] TODO.md erstellt mit detailliertem Plan

---

## 📝 Notizen
- fabric_catalog.json enthält nur Anzug-Stoffe, keine Hemden-Stoffe
- Alle Katalog-Ordner (garments, shirts, options, knowledge) sind aktuell leer
- Hemden-Stoffe müssen aus Google Drive importiert werden
- Preise sind nach Tier kategorisiert (Einstieg, Premium, Luxus)
