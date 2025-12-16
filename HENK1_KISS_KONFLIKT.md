# 🚨 KRITISCHES PROBLEM GEFUNDEN: HENK1 + KISS Workflow Konflikt

## Problem

### **Log-Symptome:**
```
=== HENK1 PROCESS: henk1_rag_queried = True
... (mehrmals)
[Keine RAG-Logs!]
[Wiederholende Fragen]
[SupervisorAgent] Decision parsing failed: input_value='henk1|clarification'
```

### **Root Cause 1: Supervisor JSON-Format (✅ BEHOBEN)**
Prompt war missverständlich:
```python
# VORHER:
"next_destination": "henk1|design_henk|rag_tool|..."
# LLM dachte Pipe ist Teil des Wertes! Gab zurück: "henk1|clarification"
```

**Fix:** Klarer JSON-Block mit Kommentaren (commit 887b0f3)

### **Root Cause 2: HENK1 vs. KISS Workflow (⚠️ OFFEN!)**

**Das System nutzt `workflow/workflow.py` mit `nodes_kiss.py`**

Im KISS-Workflow:
- ✅ **Nur Supervisor** entscheidet Routing
- ❌ Agent `action` wird IGNORIERT!

**HENK1 tut aber:**
```python
# agents/henk1.py:273-281
return AgentDecision(
    next_agent="henk1",      # ← Will sich selbst nochmal ausführen
    action="rag_tool",       # ← Wird im KISS-Workflow IGNORIERT!
    action_params=...,
    should_continue=True,
)
```

**Was passiert:**
1. HENK1 gibt `next_agent="henk1"` zurück
2. Workflow routet zurück zum Supervisor
3. Supervisor routet zu `henk1` (weil HENK1 das wollte)
4. HENK1 läuft nochmal → Wiederholende Fragen!
5. **RAG wird NIE getriggert!**

---

## Warum wird RAG nicht getriggert?

### **Supervisor Pre-Route Logik:**
```python
# supervisor_agent.py:172-195
fabric_keywords = ["stoff", "stoffe", "fabric", ...]
if _matches(fabric_keywords):
    return SupervisorDecision(
        next_destination="rag_tool",
        ...
    )
```

**Das funktioniert NUR wenn:**
- User explizit "Stoffe" sagt
- ABER NICHT wenn HENK1 selbst entscheidet "jetzt Stoffe zeigen"

### **Im KISS-Workflow:**
```python
# nodes_kiss.py:305-320
if decision.next_destination in TOOL_REGISTRY:
    # Tool direkt ausführen
    return HandoffAction(kind="tool", name=decision.next_destination, ...)
```

Supervisor muss also `next_destination="rag_tool"` zurückgeben!

Aber wenn User nur sagt "ja, blau" (ohne "Stoffe" zu erwähnen), routet Supervisor zu `henk1`!

---

## Lösungsansätze

### **Option 1: State-basiertes Supervisor-Routing (EMPFOHLEN)**

Supervisor sollte nicht nur User-Message prüfen, sondern auch **Session State**:

```python
# supervisor_agent.py:_pre_route() erweitern
def _pre_route(self, user_message, state):
    # ... existing logic ...

    # ✅ NEU: State-basierte Entscheidung
    if state.henk1_rag_queried and not state.henk1_fabrics_shown:
        # HENK1 hat RAG schon getriggert, aber Stoffe noch nicht gezeigt
        # → Direkt zu rag_tool!
        return SupervisorDecision(
            next_destination="rag_tool",
            reasoning="HENK1 triggered RAG, now executing it",
            action_params={"query": user_message},  # From state.rag_context
            confidence=0.98,
        )
```

### **Option 2: HENK1 Logik ändern (AUFWÄNDIGER)**

HENK1 sollte im KISS-Mode NICHT selbst RAG triggern:

```python
# agents/henk1.py anpassen
if intent.wants_fabrics:
    # NICHT mehr direkt RAG triggern!
    # Stattdessen: Dem Supervisor signalisieren
    state.henk1_wants_rag = True
    return AgentDecision(
        next_agent=None,  # ← Zurück zum Supervisor
        message=reply + "\n\nIch stelle dir gleich passende Stoffe zusammen...",
        should_continue=False,
    )
```

Dann Supervisor prüft `state.henk1_wants_rag` und routet zu `rag_tool`.

### **Option 3: Beide Workflows vereinen (LANGFRISTIG)**

Entweder:
- `nodes.py` verwenden (komplex, aber `action` wird genutzt)
- ODER `nodes_kiss.py` erweitern um Agent-Actions zu unterstützen

---

## Empfehlung: SOFORT-FIX (Option 1)

**In supervisor_agent.py:_pre_route() hinzufügen:**

```python
# Zeile 153-165 (nach ersten Checks)

# State-based RAG trigger detection
if (
    state.henk1_rag_queried
    and not state.henk1_fabrics_shown
    and hasattr(state, 'rag_context')
    and state.rag_context
):
    # HENK1 has prepared RAG but not shown fabrics yet
    query = state.rag_context.get("query", user_message)
    return SupervisorDecision(
        next_destination="rag_tool",
        reasoning="Executing queued RAG request from HENK1",
        action_params={"query": query},
        confidence=0.95,
    )
```

**Effekt:**
✅ RAG wird ausgeführt wenn HENK1 es vorbereitet hat
✅ Keine wiederholenden Fragen
✅ Kein Loop

---

## Test-Szenario

```
User: "Ich brauche einen Anzug für Hochzeit"
→ HENK1: "Welche Farbe?"

User: "Blau"
→ HENK1: setzt henk1_rag_queried = True, wants_fabrics = True
→ Supervisor: Prüft State, sieht henk1_rag_queried = True
→ Supervisor: Routet zu rag_tool
→ RAG: Lädt blaue Stoffe
→ HENK1: Zeigt Stoffe an
✅ Erfolg!
```

**OHNE Fix:**
```
User: "Blau"
→ HENK1: setzt henk1_rag_queried = True
→ HENK1: gibt next_agent="henk1" zurück
→ Supervisor: Routet zu henk1
→ HENK1: "Welche Farbe?" (WIEDER!)
❌ Loop!
```

---

**Erstellt:** 2025-12-16
**Status:** Supervisor-Prompt gefixt, State-basiertes Routing nötig
**Commit:** 887b0f3 (Supervisor JSON-Format)
**Nächster Fix:** State-basiertes RAG-Routing in Supervisor
