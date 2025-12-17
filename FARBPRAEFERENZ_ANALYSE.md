# Analyse: Farbpräferenz-Speicherung und Stoffbild-Workflow

## Problem 1: Farben werden nicht konsistent gespeichert/angezeigt

### Ursache
Die Farbpräferenzen werden zwar in `design_preferences.preferred_colors` gespeichert, aber es gibt mehrere Probleme:

1. **Speicherung funktioniert grundsätzlich** (`tools/fabric_preferences.py:134-141`):
   - Zeile 134-137: Gespeicherte Farben werden aus Session geladen
   - Zeile 139-141: Neue Farben werden in Session gespeichert
   ```python
   if colors and normalized_state and not normalized_state.design_preferences.preferred_colors:
       normalized_state.design_preferences.preferred_colors = colors
       logger.info(f"[FabricPrefs] Stored color preferences in session: {colors}")
   ```

2. **ABER: Session-Update kann verloren gehen**:
   - In `workflow/nodes.py:660-664` wird die aktualisierte Session zurückgegeben
   - Wenn die Session nach dem RAG-Aufruf nicht richtig persistiert wird, gehen Farben verloren

3. **Möglicher Bug im Workflow**:
   - Die Session wird nur aktualisiert, wenn `session_state is not None` (Zeile 663)
   - Bei mehrfachen Durchläufen könnte die Session-Instanz nicht konsistent sein

### Lösung

**Sofortmaßnahme:**
1. Prüfe ob `session_state` nach jedem RAG-Aufruf wirklich gespeichert wird
2. Stelle sicher, dass die Session in der Datenbank persistiert wird (wenn verwendet)
3. Aktiviere Debug-Logging für Farbspeicherung:
   ```python
   logger.info(f"[HENK1] Stored colors in session: {state.design_preferences.preferred_colors}")
   ```

**Langfristige Lösung:**
- Zentralisiere Session-Management, sodass Updates automatisch persistiert werden
- Verwende einen Session-Store (Redis, DB) statt In-Memory-State

---

## Problem 2: Stoffbilder - Ladevorgang und Empfehlungen

### Aktueller Ablauf (funktioniert, aber komplex)

#### Schritt 1: RAG Tool wird getriggert
**Datei:** `agents/henk1.py:261-269`
```python
return AgentDecision(
    next_agent="henk1",
    message=reply,
    action="rag_tool",  # Trigger RAG tool
    action_params=intent.search_criteria,
    should_continue=True,
)
```

#### Schritt 2: RAG Tool lädt Stoffe aus DB
**Datei:** `workflow/nodes.py:643-789` (Funktion `_execute_rag_tool`)

- **Zeile 660-662**: Farbpräferenzen werden extrahiert
  ```python
  criteria, session_state, excluded_colors, filters = build_fabric_search_criteria(
      query, params, state.get("session_state")
  )
  ```

- **Zeile 678**: Stoffe werden aus Datenbank geladen
  ```python
  recommendations = await rag.search_fabrics(criteria)
  ```

- **Zeile 725-729**: Ergebnisse werden in Session gespeichert
  ```python
  session_state.rag_context = rag_result
  session_state.henk1_rag_queried = True
  state["rag_output"] = rag_result
  session_state.rag_context["fabric_suggestions"] = select_dual_fabrics(recommendations)
  state["session_state"] = session_state
  ```

- **Zeile 760-786**: Stoffbilder werden vorbereitet
  - Lokale Bilder aus `/storage/fabrics/images/`
  - Format: `/fabrics/images/{fabric_code}.jpg`
  - Fallback zu externen URLs aus Datenbank

#### Schritt 3: Stoffbilder werden in HENK1 angezeigt
**Datei:** `agents/henk1.py:126-166`

**🔴 BUG GEFUNDEN in Zeile 132!**
```python
# Zeile 129-132:
rag_context = getattr(state, "rag_context", None) or {}
suggestions = rag_context.get("fabric_suggestions") or []

logger.info("[HENK1] Fabrics in rag_context: %d", len(fabrics))  # ❌ 'fabrics' existiert nicht!
```

**Fehler:** Variable `fabrics` wird verwendet, aber nicht definiert. Es sollte `suggestions` sein!

#### Schritt 4: Fabric Pair wird angezeigt
**Datei:** `workflow/nodes.py:1184-1230` (Funktion `_execute_show_fabric_pair`)

- **Zeile 1193-1194**: Holt Vorschläge aus Session
  ```python
  rag_context = getattr(session_state, "rag_context", {}) or {}
  suggestions = params.get("fabric_suggestions") or rag_context.get("fabric_suggestions") or []
  ```

- **Zeile 1203-1216**: Erstellt Cards für Mid + Luxury Tier
- **Zeile 1218-1230**: Formatiert Nachricht mit beiden Optionen

### Datenstruktur der Stoffempfehlungen

**In `rag_context` wird gespeichert:**
```python
{
    "fabrics": [
        {
            "fabric_code": "ABC123",
            "name": "Navy Blazer Stoff",
            "color": "navy",
            "pattern": "uni",
            "composition": "100% Wool",
            "weight": 280,
            "image_urls": [...],
            "local_image_paths": [...],
            "price_tier": "mid",
            "similarity_score": 0.95
        },
        # ... mehr Stoffe
    ],
    "fabric_suggestions": [
        {
            "tier": "mid",
            "fabric": {...},  # Fabric-Objekt von oben
            "title": "Allrounder (modern) für Business"
        },
        {
            "tier": "luxury",
            "fabric": {...},
            "title": "Luxus-Statement für Business"
        }
    ],
    "query": "blau business anzug",
    "colors": ["navy"],
    "patterns": ["uni"]
}
```

### Lösungen für Stoffbild-Probleme

**1. Bugfix in henk1.py:132**
```python
# ALT (Zeile 132):
logger.info("[HENK1] Fabrics in rag_context: %d", len(fabrics))  # ❌

# NEU:
logger.info("[HENK1] Suggestions in rag_context: %d", len(suggestions))  # ✅
```

**2. Verbesserte Fehlerbehandlung**
- Prüfe ob `fabric_suggestions` leer ist BEVOR Bilder angezeigt werden
- Zeige klare Fehlermeldung wenn keine Bilder verfügbar

**3. Konsistente Bilddaten**
- Stelle sicher dass `select_dual_fabrics()` immer 2 Stoffe zurückgibt (mid + luxury)
- Fallback wenn nur 1 Tier verfügbar ist

---

## Problem 3: Weiterleitung zwischen Agenten fehlt

### Aktuelles Routing-System

#### Supervisor Agent (`agents/supervisor_agent.py`)
Der Supervisor ist das "Gehirn" des Routing-Systems.

**Routing-Logik:**
1. **Pre-Route** (Zeile 152-214): Keyword-basiertes Routing für häufige Anfragen
   - Stoffe/Bilder → `rag_tool`
   - Preis → `pricing_tool`
   - Vergleich → `comparison_tool`
   - Maße → `laserhenk`

2. **LLM-basiertes Routing** (Zeile 95-150): Intelligente Analyse mit GPT-4
   - Analysiert Konversationshistorie
   - Entscheidet nächsten Agent/Tool
   - Berücksichtigt Phase Assessment

3. **Hard Gates** (Zeile 255-263): Erzwungene Reihenfolge
   ```python
   if decision.next_destination == "design_henk" and not assessment.is_henk1_complete:
       decision.next_destination = "henk1"
       decision.reasoning = "HENK1 essentials incomplete, rerouting to henk1"
   ```

#### Phase Assessment (`backend/agents/operator_phase_assessor.py`)
Prüft ob Phase abgeschlossen ist:

**HENK1 ist komplett wenn:**
- Anlass vorhanden (`occasion`)
- Timing vorhanden (`event_date` oder `event_date_hint`)
- Farbe vorhanden (`preferred_colors`)
- Budget ist optional

**Design Henk Phase:**
- Stoffauswahl getroffen
- Design-Präferenzen festgelegt

### Aktueller Workflow-Ablauf

```
1. User Message
   ↓
2. validate_query_node (prüft Eingabe)
   ↓
3. smart_operator_node (Supervisor routet)
   ↓
4a. conversation_node (Agent verarbeitet) → Tool-Anfrage?
    ↓                                           ↓
4b. Zurück zu Agent                     tools_dispatcher_node
    ↓                                           ↓
5. Zurück zu Supervisor              Zurück zu Agent (Zeile 617-637)
   ↓
6. Nächster Agent oder END
```

### Problem: Weiterleitung funktioniert nicht immer

**Mögliche Ursachen:**

1. **Hard Gate blockiert vorzeitig**
   - Wenn `preferred_colors` nicht gespeichert wird → HENK1 nie "complete"
   - Supervisor routet immer zurück zu HENK1

2. **Agent gibt falsches `next_agent` zurück**
   - HENK1 sollte nach Stoffauswahl zu Design HENK weiterleiten
   - Aktuell: HENK1 gibt `None` zurück und wartet auf User (Zeile 175-180)

3. **User muss explizit zur nächsten Phase überleiten**
   - System wartet auf User-Input statt automatisch weiterzuleiten
   - Könnte verbessert werden mit automatischer Weiterleitung

### Lösungen für Routing-Probleme

**1. Automatische Weiterleitung nach Stoffauswahl**

In `agents/henk1.py:169-180` sollte nach Stoffbild-Anzeige automatisch weitergeleitet werden:

```python
# AKTUELL (wartet auf User):
if state.henk1_rag_queried and state.henk1_mood_board_shown:
    return AgentDecision(
        next_agent=None,  # ❌ Wartet
        message=None,
        action=None,
        should_continue=False,
    )

# VORSCHLAG (mit Auto-Weiterleitung):
if state.henk1_rag_queried and state.henk1_mood_board_shown:
    # Check if user has responded to fabric images
    last_user_msg = next(
        (msg for msg in reversed(state.conversation_history)
         if msg.get("role") == "user"),
        None
    )

    # If user responded after fabric images → forward to Design Henk
    if last_user_msg:
        return AgentDecision(
            next_agent="design_henk",  # ✅ Weiterleitung
            message="Perfekt! Lass uns jetzt über den Schnitt sprechen...",
            action=None,
            should_continue=True,  # ✅ Fortsetzen
        )

    # Otherwise wait for user response
    return AgentDecision(
        next_agent=None,
        message=None,
        action=None,
        should_continue=False,
    )
```

**2. Supervisor-Logik verbessern**

In `agents/supervisor_agent.py` könnte man explizite Übergangsregeln hinzufügen:

```python
# Nach Stoffauswahl in HENK1 → automatisch zu Design Henk
if (state.henk1_rag_queried and
    state.henk1_mood_board_shown and
    user_message_indicates_fabric_decision):

    return SupervisorDecision(
        next_destination="design_henk",
        reasoning="Fabric selection complete, moving to design phase",
        confidence=0.95
    )
```

**3. Phase Assessment Log verbessern**

Aktuell ist schwer zu debuggen warum Phase nicht "complete" ist.

Vorschlag: Detaillierte Logs in `operator_phase_assessor.py`:

```python
logger.info(f"[PhaseAssessment] HENK1 Status:")
logger.info(f"  - occasion: {occasion} ({'✓' if occasion else '✗'})")
logger.info(f"  - timing: {timing} ({'✓' if timing else '✗'})")
logger.info(f"  - colors: {colors} ({'✓' if colors else '✗'})")
logger.info(f"  - is_complete: {is_henk1_complete}")
```

---

## Zusammenfassung: Kritische Bugs und Lösungen

### 🔴 Bug 1: Variable `fabrics` nicht definiert
**Datei:** `agents/henk1.py:132`
```python
# VORHER:
logger.info("[HENK1] Fabrics in rag_context: %d", len(fabrics))

# NACHHER:
logger.info("[HENK1] Suggestions in rag_context: %d", len(suggestions))
```

### 🔴 Bug 2: Farbpräferenzen gehen verloren
**Ursache:** Session wird nicht persistiert nach RAG-Update
**Lösung:** Stelle sicher dass `state["session_state"]` nach `build_fabric_search_criteria` zurückgeschrieben wird

### 🔴 Bug 3: Keine automatische Weiterleitung zu Design Henk
**Ursache:** HENK1 gibt `next_agent=None` zurück und wartet auf User
**Lösung:** Nach Stoffauswahl + User-Feedback automatisch zu `design_henk` weiterleiten

---

## Empfohlene Fixes (Priorität)

### Priorität 1: Variable-Bug beheben
```bash
# henk1.py:132
- len(fabrics)
+ len(suggestions)
```

### Priorität 2: Session-Logging verbessern
```python
# Nach build_fabric_search_criteria:
logger.info(f"[FabricPrefs] Session colors after update: {session_state.design_preferences.preferred_colors}")
```

### Priorität 3: Automatische Weiterleitung implementieren
- Nach Stoffbild-Anzeige + User-Response → Design Henk
- Supervisor sollte dies automatisch erkennen

### Priorität 4: Phase Assessment detaillierter loggen
- Zeige genau welche Felder fehlen für Phase-Übergang
- Hilft beim Debuggen von Routing-Problemen

---

## Testing-Hinweise

### Test 1: Farbpräferenz-Persistenz
1. Sage "Ich möchte einen blauen Anzug"
2. Lasse dir Stoffe zeigen
3. Sage "Zeig mir graue Stoffe"
4. Prüfe: Werden blaue UND graue Farben gespeichert?

### Test 2: Stoffbild-Anzeige
1. Sage "Zeig mir Stoffe für Hochzeit"
2. Prüfe: Werden 2 Bilder angezeigt (mid + luxury)?
3. Prüfe: Sind Titel, Material, Gewicht, Referenznummer vorhanden?

### Test 3: Weiterleitung zu Design Henk
1. Sage "Ich brauche einen Anzug für Business in blau"
2. Lasse dir Stoffe zeigen
3. Sage "Der erste gefällt mir"
4. Prüfe: Wechselt das System zu Design Henk?
5. Prüfe: Bleiben die Farbpräferenzen erhalten?

---

**Erstellt:** 2025-12-16
**System:** Laserhenk Maßanzug-Konfigurator
**Version:** Flask + LangGraph Workflow
