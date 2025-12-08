# Laserhenk - Agentic AI System

## 🎯 Überblick

Laserhenk ist ein **agentic AI System** basierend auf **LangGraph** für die automatisierte Kundenberatung und Auftragsabwicklung im Maßschneider-Bereich.

Das System nutzt **Pydantic-Klassen** für strukturierte Datenvalidierung und mehrere spezialisierte KI-Agenten für unterschiedliche Phasen des Kundenprozesses.

## 🏗️ Architektur

### Agent-Hierarchie

```
┌─────────────────────────────────────────────────────────┐
│                    OPERATOR AGENT                        │
│              (Routing & Orchestrierung)                  │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┬──────────────┐
        │                     │              │
┌───────▼──────┐    ┌────────▼───────┐   ┌─▼─────────────┐
│    HENK1     │    │  DESIGN HENK   │   │  LASERHENK    │
│ Bedarfs-     │───▶│  Design &      │──▶│  Maß-         │
│ ermittlung   │    │  Leadsicherung │   │  erfassung    │
└──────────────┘    └────────────────┘   └───────────────┘
```

### 1. **Operator Agent**
- **Rolle**: Zentraler Router
- **Aufgabe**: Entscheidet, welcher spezialisierte Agent aktiv wird
- **Logik**: Basiert auf `SessionState` und Customer Journey Phase

### 2. **HENK1 Agent** (Bedarfsermittlung)
- **AIDA-Prinzip**: Attention, Interest, Desire, Action
- **Aufgaben**:
  - Smalltalk & Eisbrechen
  - Verstehen der Kundenbedürfnisse
  - Unterscheidung: Neukunde vs. Bestandskunde
  - Erste Bildgenerierung mit wenigen Kundeninfos

### 3. **Design HENK Agent** (Design & Leadsicherung)
- **RAG Integration**: Nutzt PostgreSQL-Datenbank für Designoptionen
- **Kundenabfrage**:
  - Reversbreite
  - Schulterpolster
  - Hosenbund
  - Innenfutter
  - Weitere Details
- **DALLE Integration**: Moodbild-Generierung (alte + neue Infos)
- **⭐ LEADSICHERUNG**: PIPEDRIVE CRM Integration

### 4. **LASERHENK Agent** (Maßerfassung)
- **SAIA 3D Tool**: 3D-Körperscan für präzise Maße
- **HITL Option**: Human-in-the-Loop Termin beim Kunden
- **Fallback**: Manuelle Maßeingabe

## 📁 Projektstruktur

```
laserhenk/
├── agents/                     # Agent-Implementierungen
│   ├── __init__.py
│   ├── base.py                # BaseAgent Klasse
│   ├── operator.py            # Operator Agent (Router)
│   ├── henk1.py               # HENK1 (Bedarfsermittlung)
│   ├── design_henk.py         # Design HENK (Design + CRM)
│   ├── laserhenk.py           # LASERHENK (Maße)
│   └── supervisor_agent.py    # Supervisor Agent
│
├── tools/                      # Tool-Interfaces
│   ├── __init__.py
│   ├── rag_tool.py            # PostgreSQL RAG
│   ├── crm_tool.py            # PIPEDRIVE CRM
│   ├── dalle_tool.py          # DALLE Image Generation
│   └── saia_tool.py           # SAIA 3D Measurement
│
├── models/                     # Pydantic Models
│   ├── __init__.py
│   ├── customer.py            # Customer, Measurements, DesignPreferences
│   ├── tools.py               # Tool Request/Response Models
│   ├── graph_state.py         # LangGraph State
│   ├── fabric.py              # Fabric Models
│   ├── business.py            # Business Models
│   ├── handoff.py             # Handoff Models
│   └── auth.py                # Authentication Models
│
├── workflow/                   # LangGraph Workflow
│   ├── __init__.py
│   ├── workflow.py            # Workflow Definition
│   ├── nodes.py               # Workflow Nodes
│   └── graph_state.py         # Graph State Management
│
├── database/                   # Database Connection
│   ├── __init__.py
│   └── connection.py          # PostgreSQL Connection Pool
│
├── drive_mirror/               # Google Drive Mirror
│   ├── chunks/                # RAG Chunks (generated)
│   └── henk/
│       ├── fabrics/           # ✅ Fabric Catalog (140 Anzug-Stoffe)
│       │   ├── fabric_catalog.json
│       │   └── price_book_by_tier.json
│       ├── garments/          # 🆕 Garment Catalog (Template)
│       │   └── garment_catalog.json
│       ├── shirts/            # 🆕 Shirt Catalog (Template)
│       │   └── shirt_catalog.json
│       ├── options/           # 🆕 Options Catalog (Template)
│       │   └── henk2_options_catalog.json
│       └── knowledge/         # 🆕 Style Catalog (Template)
│           └── style_catalog.json
│
├── scripts/                    # Utility Scripts
│   ├── generate_fabric_embeddings.py
│   ├── verify_embeddings.py
│   ├── inspect_db.py
│   ├── sync_google_drive_pricing.py
│   └── test_llm_connection.py
│
├── tests/                      # Unit Tests
│   ├── __init__.py
│   └── test_workflow.py
│
├── docs/                       # Documentation
│   ├── DATABASE_ANALYSIS.md
│   ├── RAG_SETUP.md
│   └── CLEANUP_DONE.md
│
├── .env.example               # ✅ Vollständiges Environment Template
├── .env.minimal               # Minimale LLM-Test Config
├── TODO.md                    # 🆕 Detaillierter Entwicklungsplan
├── CLEANUP_SUMMARY.md         # ✅ Cleanup & Update Zusammenfassung
├── QUICK_START.md             # Quick Start Guide
├── TEST_GUIDE.md              # Testing Guide
├── requirements.txt           # Python Dependencies
└── README.md                  # Diese Datei
```

## 🔧 Tools & Integrationen

### 1. RAG Tool (PostgreSQL)
- **Status**: ✅ Bereits vorhanden
- **Funktion**: Produktkatalog, Design-Optionen, Kundendaten
- **Interface**: `RAGQuery` / `RAGResult`

### 2. CRM Tool (PIPEDRIVE)
- **Status**: ✅ Bereits vorhanden
- **Funktion**: Leadsicherung, Produktion, After Sales, HITL
- **Interface**: `CRMLeadCreate` / `CRMLeadUpdate` / `CRMLeadResponse`

### 3. DALLE Tool (OpenAI)
- **Status**: 🚧 Interface erstellt
- **Funktion**: Moodbild-Generierung aus strukturiertem Input
- **Interface**: `DALLEImageRequest` / `DALLEImageResponse`

### 4. SAIA Tool (3D Measurement)
- **Status**: 🔜 Zukünftig
- **Funktion**: 3D-Körperscan für präzise Maße
- **Interface**: `SAIAMeasurementRequest` / `SAIAMeasurementResponse`

## 🗂️ Pydantic Models

### Core Models (`models/customer.py`)
- **`Customer`**: Basis-Kundeninformationen
- **`CustomerType`**: Enum (NEW, EXISTING)
- **`Measurements`**: Körpermaße (SAIA oder manuell)
- **`DesignPreferences`**: Revers, Futter, Schulter, etc.
- **`SessionState`**: Gesamter Session-Zustand

### Tool Models (`models/tools.py`)
- **RAG**: `RAGQuery`, `RAGResult`
- **CRM**: `CRMLeadCreate`, `CRMLeadUpdate`, `CRMLeadResponse`
- **DALLE**: `DALLEImageRequest`, `DALLEImageResponse`
- **SAIA**: `SAIAMeasurementRequest`, `SAIAMeasurementResponse`

### LangGraph State (`models/graph_state.py`)
- **`HenkGraphState`**: TypedDict für LangGraph State Management
- **`create_initial_graph_state()`**: Factory für neue Sessions

## 🚀 Setup

### 1. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
cp .env.example .env
# Editiere .env mit echten API Keys
```

### 3. Konfiguration

Bearbeite `.env`:
- `OPENAI_API_KEY`: Für LLM & DALLE
- `POSTGRES_CONNECTION_STRING`: RAG Datenbank
- `PIPEDRIVE_API_KEY`: CRM Integration
- `SAIA_API_KEY`: (zukünftig) 3D Measurement

## 📝 Nächste Schritte

### Phase 2: Strukturierter Payload & Handoffs
- [ ] Handoff-Logik zwischen Agenten definieren
- [ ] RAG → LLM Payload-Struktur
- [ ] Mandatory vs. Nice-to-have User Inputs
- [ ] LangGraph Workflow-Definition

### Phase 3: LLM Integration
- [ ] Prompts aus Google Drive HENK einbinden
- [ ] LangChain Integration für LLM Calls
- [ ] Conversation History Management

### Phase 4: Tool-Implementierung
- [ ] DALLE Tool: Prompt-Engineering & API Integration
- [ ] RAG Tool: Connection Pool & Query Logic
- [ ] CRM Tool: PIPEDRIVE API Calls

### Phase 5: Testing & Deployment
- [ ] Unit Tests für Agents
- [ ] Integration Tests für Tools
- [ ] End-to-End Test: Customer Journey

## 📚 Referenzen

- **LangGraph**: https://docs.langchain.com/oss/python/langgraph/workflows-agents
- **Pydantic**: https://docs.pydantic.dev/
- **PIPEDRIVE API**: https://developers.pipedrive.com/

## 💡 Designprinzipien

- **Pythonic Code**: PEP8-konform, lesbar, wartbar
- **Type Safety**: Pydantic für alle Datenstrukturen
- **Separation of Concerns**: Agents, Tools, Models getrennt
- **MVP First**: Nur essenzielle Features im ersten Schritt
- **Testbarkeit**: Klare Interfaces für Mocking & Testing

## 🎯 MVP Scope

**Dieser Stand**: Nur Architektur & Pydantic-Klassen
- ✅ Ordnerstruktur
- ✅ Pydantic Models
- ✅ Agent-Basisstrukturen
- ✅ Tool-Interfaces

**Nicht in diesem Schritt**:
- ❌ Konkrete LLM-Implementierung
- ❌ Tool-API-Integration
- ❌ LangGraph Workflow-Execution
- ❌ Frontend/UI

---

## 🆕 Latest Updates (2025-12-08)

### ✅ Environment Configuration
- **`.env.example`** vollständig aktualisiert mit allen Secrets
- Neue Sections: OpenAI, Database Pool, Embeddings, Google Drive, API Server, Security, Performance, Feature Flags
- **`.env.minimal`** für schnelle LLM-Tests

### ✅ Katalog-Templates erstellt
Alle fehlenden Kataloge haben jetzt vollständige JSON-Templates:
- **Garment Catalog** - Anzüge, Hemden, Hosen, Sakkos, Westen, Mäntel
- **Shirt Catalog** - Hemden-Stoffe (72SH, 70SH, 73SH, 74SH) + Konfigurationen
- **Options Catalog** - HENK2 Maßkonfektion-Optionen
- **Style Catalog** - Dress Codes, Farb-Kombinationen, Style Rules, Body Types

### ✅ Code-Qualität
- Code-Formatierung mit **black** durchgeführt (24 Dateien)
- Alle **ruff** Checks bestanden
- Unused Imports entfernt
- Bare except-Statements behoben

### ✅ Dokumentation
- **TODO.md** - Detaillierter Entwicklungsplan für heute
- **CLEANUP_SUMMARY.md** - Vollständige Zusammenfassung aller Änderungen
- **README.md** - Aktualisierte Projekt-Struktur

### 📋 Nächste Schritte
Siehe **[TODO.md](TODO.md)** für den detaillierten Entwicklungsplan:
1. Google Drive nach Hemden-Stoffen durchsuchen (72SH, 70SH, 73SH, 74SH)
2. Kataloge mit echten Daten befüllen
3. Fabric Embeddings generieren: `python scripts/generate_fabric_embeddings.py`
4. RAG-System validieren: `python scripts/verify_embeddings.py`
5. Agent-Tests erweitern

---

**Version**: 1.1.0 (Cleanup & Catalog Templates)
**Datum**: 2025-12-08
