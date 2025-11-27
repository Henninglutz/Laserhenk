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
├── agents/                  # Agent-Implementierungen
│   ├── __init__.py
│   ├── base.py             # BaseAgent Klasse
│   ├── operator.py         # Operator Agent (Router)
│   ├── henk1.py            # HENK1 (Bedarfsermittlung)
│   ├── design_henk.py      # Design HENK (Design + CRM)
│   └── laserhenk.py        # LASERHENK (Maße)
│
├── tools/                   # Tool-Interfaces
│   ├── __init__.py
│   ├── rag_tool.py         # PostgreSQL RAG
│   ├── crm_tool.py         # PIPEDRIVE CRM
│   ├── dalle_tool.py       # DALLE Image Generation
│   └── saia_tool.py        # SAIA 3D Measurement
│
├── models/                  # Pydantic Models
│   ├── __init__.py
│   ├── customer.py         # Customer, Measurements, DesignPreferences
│   ├── tools.py            # Tool Request/Response Models
│   └── graph_state.py      # LangGraph State
│
├── config/                  # Konfiguration
│   ├── __init__.py
│   └── settings.py         # Pydantic Settings
│
├── tests/                   # Unit Tests
│   └── __init__.py
│
├── .env.example            # Environment Variables Template
├── requirements.txt        # Python Dependencies
└── README.md              # Diese Datei
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

**Version**: 1.0.0 (Architecture Phase)
**Datum**: 2025-11-26
