# Architecture Decision: LLM Integration Strategy

## Frage 3: Warum nicht direkt LLM Conversations?

### Aktuelle Architektur
```
State-basiert:
┌─────────┐    ┌────────┐    ┌─────┐    ┌──────────────┐
│Operator │───▶│ HENK1  │───▶│ RAG │───▶│ Design HENK  │
└─────────┘    └────────┘    └─────┘    └──────────────┘
     ▲              │                           │
     └──────────────┴───────────────────────────┘
           SessionState durchgereicht
```

### Problem: Wo kommt User Chat rein?

**Option A: Pure Conversation** ❌
```
User ───▶ LLM Chat ───▶ Antwort
             │
             └─ Wie weiß LLM wann RAG? Wann nächster Agent?
```

**Problem:** Keine klare Handoff-Logik zwischen Agents!

---

## Migration Strategy: Hybrid Approach ✅

### Phase 1: Conversation IN Agents (MVP)
```python
# workflow.py - Neuer Conversation Node
async def conversation_node(state: HenkGraphState) -> HenkGraphState:
    """Handle user chat with current agent."""
    current_agent = state["current_agent"]
    user_message = state["user_input"]

    if current_agent == "henk1":
        agent = Henk1Agent()
        decision = await agent.process_with_llm(state["session_state"], user_message)
    elif current_agent == "design_henk":
        agent = DesignHenkAgent()
        decision = await agent.process_with_llm(state["session_state"], user_message)

    # Update state based on LLM decision
    state["next_agent"] = decision.next_agent
    state["pending_action"] = decision.action

    return state
```

**Flow:**
```
User: "Ich brauche einen Anzug für eine Hochzeit"
  │
  ▼
Operator (Rule-based) ──▶ route to HENK1
  │
  ▼
HENK1 (LLM Conversation)
  │─ Prompt: "Sammle Info zu Anlass, Budget, Style"
  │─ LLM Chat mit User (mehrere Runden)
  │─ Entscheidung: "Genug Info → query_rag"
  ▼
RAG Tool
  │
  ▼
Operator ──▶ route to Design HENK
  │
  ▼
Design HENK (LLM Conversation)
  │─ RAG Kontext + User Preferences
  │─ LLM sammelt Design Details
  │─ Entscheidung: "create_crm_lead"
```

### Phase 2: Multi-Turn Conversations
```python
class HenkGraphState(TypedDict):
    # Existing
    session_state: SessionState
    messages: list[dict]

    # NEW for conversations
    conversation_mode: bool  # True = User chattet mit Agent
    user_input: Optional[str]
    awaiting_user_input: bool
```

**Workflow Update:**
```python
def route_after_agent(state):
    if state["awaiting_user_input"]:
        return "wait_for_user"  # Pause graph

    if state["pending_action"] == "query_rag":
        return "rag_tool"

    return state["next_agent"]
```

---

## Empfohlene Architektur: Layered Approach

```
┌─────────────────────────────────────────────┐
│         User Interface (Frontend)           │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│    LangGraph Workflow (Orchestration)       │
│  ┌─────────┐  ┌────────┐  ┌──────────────┐ │
│  │Operator │─▶│Conversa│─▶│  Tool Nodes  │ │
│  │ (Route) │  │tion    │  │  (RAG, CRM)  │ │
│  └─────────┘  │ Node   │  └──────────────┘ │
│               └────────┘                    │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│   PydanticAI Agents (Business Logic)        │
│  ┌────────┐  ┌──────────────┐  ┌─────────┐ │
│  │ HENK1  │  │ Design HENK  │  │LaserHENK│ │
│  │        │  │              │  │         │ │
│  │ Core + │  │  Core +      │  │ Core +  │ │
│  │Specific│  │  Specific    │  │Specific │ │
│  └────────┘  └──────────────┘  └─────────┘ │
└─────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### ✅ **Bereits implementiert:**
- PydanticAI Agents mit `process()` und `process_with_llm()`
- LangGraph State Management
- Tool Nodes (RAG)

### 🚧 **Nächste Schritte:**

#### 1. **Prompt Struktur erstellen**
```bash
mkdir -p Promt/core
mkdir -p Promt/agents

# Core Persona
Promt/core/brand_voice.md
Promt/core/customer_approach.md

# Agent-spezifisch
Promt/agents/henk1_specific.md
Promt/agents/henk2_design_specific.md
```

#### 2. **Conversation Node hinzufügen**
```python
# workflow.py
workflow.add_node("conversation", conversation_node)
workflow.add_conditional_edges("conversation", route_after_conversation)
```

#### 3. **LLM Integration aktivieren**
```python
# Aktuell: Rule-based
decision = await agent.process(state)

# Migration: LLM-based
decision = await agent.process_with_llm(state, user_message)
```

---

## Antworten auf Ihre Fragen

### 1. **Pydantic AI + LangGraph richtig?**
✅ **Ja!** Gute Architektur. Aber aktuell nutzen Sie nur Pydantic für Types, nicht für LLM.

### 2. **Core Persona wo?**
✅ **Hybrid:** Core Persona (`brand_voice.md`) + Agent-spezifisch (`henk1_specific.md`)
   → Beim Init: `core + specific` zusammensetzen

### 3. **Warum nicht LLM Conversations direkt?**
✅ **Migration nötig:** Von Rule-based (`process()`) zu LLM-based (`process_with_llm()`)
   → Aber: **Graph orchestriert weiter**, LLM macht nur Agent-Logik

---

## Nächster Schritt: Was implementieren?

**Option A:** Prompt Struktur aufbauen (Core + Specific)
**Option B:** Conversation Node in LangGraph
**Option C:** `process_with_llm()` aktivieren in HENK1

Was möchten Sie als nächstes angehen?
