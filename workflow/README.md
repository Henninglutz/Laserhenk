# HENK LangGraph Workflow - Phase 2

## Überblick

Die LangGraph Workflow-Implementierung orchestriert das HENK Agent System mit 4 spezialisierten Agenten, 4 Tool-Nodes und Human-in-the-Loop (HITL) Interrupts.

## Architektur

### Agents (Nodes)

1. **Operator Agent** (`operator_node`)
   - Routing-Agent für das gesamte System
   - Entscheidet basierend auf SessionState, welcher Agent als nächstes aktiv wird
   - Logik:
     - Neukunde ohne customer_id → HENK1
     - Bedarf ermittelt, keine Design-Präferenzen → Design HENK
     - Design abgeschlossen, keine Maße → LASERHENK
     - Alles fertig → END

2. **HENK1 Agent** (`henk1_node`)
   - Bedarfsermittlung nach AIDA-Prinzip
   - Smalltalk und Eisbrechen
   - Unterscheidung Neu-/Bestandskunde
   - Erste Bildgenerierung

3. **Design HENK Agent** (`design_henk_node`)
   - Design-Präferenzen sammeln (Revers, Futter, Schulter, Bund)
   - RAG-Datenbank für Designoptionen nutzen
   - DALLE Moodbild-Generierung
   - **Leadsicherung mit CRM (PIPEDRIVE) → HITL Interrupt**

4. **LASERHENK Agent** (`laserhenk_node`)
   - Maßerfassung
   - **Entweder/Oder Logik:**
     - SAIA 3D Tool (automatisch) ODER
     - HITL Interrupt (manueller Termin)

### Tool Nodes

1. **RAG Tool** (`rag_tool_node`)
   - PostgreSQL RAG-Datenbank
   - Produktkatalog, Design-Optionen, Kundenhistorie
   - Fabric Recommendations

2. **CRM Tool** (`crm_tool_node`)
   - PIPEDRIVE API Integration
   - Lead Creation und Updates
   - **Triggert HITL Interrupt nach Lead-Erstellung**

3. **DALLE Tool** (`dalle_tool_node`)
   - OpenAI DALLE Image Generation
   - Moodboard-Erstellung aus Design-Präferenzen
   - Kombiniert alte (RAG) + neue (Session) Infos

4. **SAIA Tool** (`saia_tool_node`)
   - 3D Body Measurement API
   - Alternative zu manuellem Termin
   - Full-Body oder Partial Scans

### HITL Interrupts

**1. Design HENK - CRM Lead Approval**
- Nach erfolgreicher Lead-Erstellung in PIPEDRIVE
- Workflow pausiert für menschliche Review
- Edge: `crm_tool → hitl_interrupt → design_henk`

**2. LASERHENK - Measurement Method**
- Entweder: SAIA 3D Tool (automatisch)
- Oder: HITL Interrupt (manueller Termin)
- Conditional Edge basierend auf `pending_action`

## Graph Flow

```
START
  ↓
operator (Routing)
  ↓ (conditional)
  ├── henk1 (Bedarfsermittlung)
  │     ↓ (conditional)
  │     ├── rag_tool → henk1
  │     ├── dalle_tool → henk1
  │     └── operator
  │
  ├── design_henk (Design + Lead)
  │     ↓ (conditional)
  │     ├── rag_tool → design_henk
  │     ├── dalle_tool → design_henk
  │     ├── crm_tool → hitl_interrupt → design_henk
  │     └── operator
  │
  ├── laserhenk (Maßerfassung)
  │     ↓ (conditional)
  │     ├── saia_tool → laserhenk → operator
  │     ├── hitl_interrupt → laserhenk → operator
  │     └── operator
  │
  └── END
```

## Conditional Edges

### 1. `route_from_operator`
Routet vom Operator zu den Agenten:
- `"henk1"` → HENK1 Agent
- `"design_henk"` → Design HENK Agent
- `"laserhenk"` → LASERHENK Agent
- `"end"` → END

### 2. `route_from_agent`
Routet von Agenten zu Tools oder zurück zum Operator:
- `"query_rag"` → RAG Tool
- `"create_crm_lead"` → CRM Tool
- `"generate_dalle_image"` → DALLE Tool
- `"request_saia_measurement"` → SAIA Tool
- Sonst → Operator

### 3. `route_laserhenk_measurement`
Spezielle LASERHENK Logik:
- `"request_saia_measurement"` → SAIA Tool
- `"schedule_manual_measurement"` → HITL Interrupt
- Sonst → Operator

### 4. `route_from_tools`
Routet von Tools zurück zum aufrufenden Agent:
- Basiert auf `current_agent` im State
- Kehrt zurück zu: `henk1`, `design_henk`, `laserhenk`, oder `operator`

## State Management

Die `HenkGraphState` verwaltet:
- `session_state`: Core SessionState mit Customer, Preferences, Measurements
- `messages`: LangGraph-managed Message-Liste
- `current_agent`: Aktuell aktiver Agent
- `next_agent`: Nächster Agent (vom Operator bestimmt)
- `pending_action`: Aktion, die ausgeführt werden soll
- `action_params`: Parameter für die Aktion
- Tool-Outputs: `rag_output`, `crm_output`, `dalle_output`, `saia_output`

## Checkpointing & Interrupts

- **MemorySaver Checkpointer**: Ermöglicht Pause/Resume
- **interrupt_before**: `["hitl_interrupt"]`
- **Thread ID**: Identifiziert Workflow-Session für Resume

## Verwendung

### Workflow starten

```python
from workflow.graph import run_henk_workflow
from models.graph_state import create_initial_graph_state

# Initial state erstellen
initial_state = create_initial_graph_state("session_123")

# Workflow ausführen
final_state = await run_henk_workflow(
    initial_state=initial_state,
    thread_id="session_123"
)
```

### Workflow fortsetzen nach HITL

```python
from workflow.graph import resume_henk_workflow

# Nach human approval
final_state = await resume_henk_workflow(
    thread_id="session_123",
    user_input={"role": "user", "content": "Approved"}
)
```

## HITL Interrupt Szenarien

### Szenario 1: CRM Lead Approval (Design HENK)

1. Design HENK sammelt Präferenzen
2. DALLE generiert Moodbild
3. CRM Tool erstellt Lead in PIPEDRIVE
4. **HITL Interrupt** → Workflow pausiert
5. Human reviewed Lead in PIPEDRIVE
6. Human approved → Workflow fortsetzt
7. Zurück zu Design HENK → Operator

### Szenario 2: LASERHENK Measurement Method

**Option A: SAIA 3D Tool**
1. LASERHENK entscheidet: SAIA verfügbar
2. → SAIA Tool Node
3. 3D Scan durchgeführt
4. Maße verfügbar → Operator

**Option B: HITL Manual Measurement**
1. LASERHENK entscheidet: Manuelle Messung nötig
2. → HITL Interrupt Node
3. Workflow pausiert
4. Human vereinbart Termin
5. Workflow fortsetzt → LASERHENK → Operator

## Nächste Schritte

1. LLM Integration für intelligente Agent-Entscheidungen
2. Externe API-Anbindungen (PIPEDRIVE, DALLE, SAIA)
3. RAG Database Setup mit pgvector
4. UI für HITL Interaktionen
5. Testing & Validation Framework
