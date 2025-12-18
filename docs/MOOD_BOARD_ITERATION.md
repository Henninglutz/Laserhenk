# Moodboard Iterationsschleife - Dokumentation

## Übersicht

Die Moodboard-Iterationsschleife ermöglicht es Benutzern, das generierte Moodboard bis zu **7 Mal** zu iterieren und Verbesserungswünsche zu äußern, bevor sie es genehmigen. Nach der Genehmigung erfolgt die automatische Leadsicherung in Pipedrive CRM und die Weiterleitung zur Terminvereinbarung mit LASERHENK.

## User Flow

```
Design-Präferenzen sammeln (Revers, Schulter, Hosenbund)
    ↓
Moodboard generieren (Iteration 1)
    ↓
Moodboard anzeigen + Genehmigung anfragen
    ↓
User-Entscheidung:
    ├─ Genehmigung ("Ja", "Perfekt", "OK")
    │   ↓
    │   CRM Lead erstellen (Pipedrive)
    │   ↓
    │   Terminvereinbarung vorbereiten
    │   ↓
    │   Handoff zu LASERHENK
    │
    └─ Feedback ("Ändern", "Anders", detailliertes Feedback)
        ↓
        Feedback in Prompt integrieren
        ↓
        Moodboard neu generieren (Iteration 2-7)
        ↓
        Zurück zu "Moodboard anzeigen"
```

## Implementierte Features

### 1. Iterations-Counter (Max. 7 Iterationen)

**Datei:** `models/customer.py`

Neue Felder in `ImageGenerationState`:
- `mood_board_iteration_count: int` - Zählt die Anzahl der Generierungen
- `mood_board_approved: bool` - Markiert die Genehmigung durch den User
- `mood_board_feedback: Optional[str]` - Speichert User-Feedback für die nächste Iteration

```python
class ImageGenerationState(BaseModel):
    mood_image_url: Optional[str]
    image_generation_history: list[dict]
    mood_board_iteration_count: int = Field(default=0)
    mood_board_approved: bool = Field(default=False)
    mood_board_feedback: Optional[str] = Field(None)
```

### 2. Design HENK Agent - Iterationslogik

**Datei:** `agents/design_henk.py`

Der Design HENK Agent wurde erweitert um:

#### Iteration Loop
- Prüft `mood_board_iteration_count` gegen Maximum (7)
- Bei Erreichen des Limits: Automatische Genehmigung mit Info-Nachricht
- Inkrement des Counters bei jeder Generation

#### Feedback-Integration
- User-Feedback wird in `style_keywords` eingefügt
- Prompt wird mit Feedback angepasst
- Feedback wird nach Verwendung gelöscht

#### Approval-Handling
- Wartet auf User-Genehmigung nach Moodboard-Anzeige
- Zeigt verbleibende Iterationen an
- Nach Genehmigung: Trigger CRM Lead-Erstellung

```python
# Beispiel: Iteration mit Feedback
if state.image_state.mood_board_feedback:
    logger.info(f"[DesignHenk] Incorporating user feedback: {state.image_state.mood_board_feedback}")
    style_keywords.append(f"User feedback: {state.image_state.mood_board_feedback}")
    state.image_state.mood_board_feedback = None
```

### 3. User-Input-Erkennung (Approval vs. Feedback)

**Datei:** `workflow/nodes_kiss.py` - `route_node()`

#### Approval Keywords (Genehmigung)
```python
approval_keywords = [
    "ja", "yes", "genehmigt", "approved", "perfekt", "perfect",
    "super", "toll", "gefällt mir", "passt", "ok", "okay",
    "bestätigt", "confirmed", "genau so", "stimmt",
]
```

**Aktion:** `mood_board_approved = True` → CRM Lead erstellen

#### Feedback Keywords (Änderungswunsch)
```python
feedback_keywords = [
    "nein", "no", "nicht", "anders", "ändern", "anpassen",
    "change", "modify", "andere", "lieber", "stattdessen",
]
```

**Aktion:** Feedback speichern → Moodboard neu generieren

**Fallback:** Nachrichten > 20 Zeichen werden als detailliertes Feedback behandelt.

### 4. CRM Integration - Pipedrive

**Dateien:**
- `tools/crm_tool.py` - CRM Tool
- `models/customer.py` - Customer mit appointment_preferences

#### Lead-Erstellung
```python
async def _crm_create_lead(params: dict, state: HenkGraphState) -> ToolResult:
    lead_data = CRMLeadCreate(
        customer_name=customer_name,
        email=customer_email,
        phone=customer_phone,
        notes=f"Mood board: {mood_image_url}",
        deal_value=2000.0,
    )
    response = await crm_tool.create_lead(lead_data)
    session_state.customer.crm_lead_id = response.lead_id
```

#### Termin-Daten (Strukturiert im State)

Terminpräferenzen werden strukturiert im Customer-State gespeichert (wie `favorite_fabric`):

```python
# Strukturierte Appointment-Daten
session_state.customer.appointment_preferences = {
    "location": "Kunde zu Hause",  # oder "Im Büro"
    "preferred_date": "2024-01-15",
    "preferred_time": "14:00",
    "notes": "Maßerfassung für Business-Anzug",
}
```

**Terminierung über CRM:**
- Termine werden über Pipedrive CRM verwaltet
- Google Calendar Sync läuft automatisch über CRM
- Keine separate Appointment-API nötig

**Tool Actions:**
- `crm_create_lead` - Lead-Erstellung in Pipedrive

### 5. Handoff zu LASERHENK

**Datei:** `agents/design_henk.py`

Nach erfolgreicher Genehmigung und CRM-Lead-Erstellung:

```python
if state.customer.crm_lead_id:
    return AgentDecision(
        next_agent=None,
        message="✅ Design-Phase abgeschlossen!\n\n"
               "Als nächstes vereinbaren wir einen Termin mit Henning für die Maßerfassung. "
               "Bevorzugen Sie einen Termin bei Ihnen zu Hause oder im Büro?",
        action="complete_design_phase",
        should_continue=False,
    )
```

## Datenfluss

### State-Änderungen während der Iteration

| Schritt | State-Änderungen |
|---------|------------------|
| 1. Erste Generation | `iteration_count = 1`, `mood_image_url = <URL>` |
| 2. User gibt Feedback | `mood_board_feedback = "<Text>"` |
| 3. Re-Generation | `iteration_count = 2`, `mood_image_url = <neue_URL>`, `mood_board_feedback = None` |
| 4. User genehmigt | `mood_board_approved = True` |
| 5. CRM Lead | `customer.crm_lead_id = <ID>` |
| 6. Handoff | `current_agent = "laserhenk"` |

## Konfiguration

### Umgebungsvariablen (Pipedrive)

```bash
PIPEDRIVE_API_KEY=<your_api_key>
PIPEDRIVE_DOMAIN=api.pipedrive.com  # Optional, default
```

### Maximale Iterationen

Änderbar in `agents/design_henk.py`:
```python
if state.image_state.mood_board_iteration_count >= 7:  # ← Hier ändern
```

## Testing

### Manuelle Tests

1. **Approval-Flow:**
   ```
   User: "Ja, perfekt!"
   → mood_board_approved = True
   → CRM Lead erstellen
   ```

2. **Feedback-Flow:**
   ```
   User: "Könnte der Anzug etwas dunkler sein?"
   → mood_board_feedback = "<Text>"
   → Moodboard neu generieren mit Feedback
   ```

3. **Max-Iterationen:**
   - 7 Mal Feedback geben
   - System sollte automatisch genehmigen mit Info-Nachricht

### Unit Tests (TODO)

```python
def test_mood_board_approval_detection():
    assert detects_approval("Ja, perfekt!") == True
    assert detects_approval("Das gefällt mir nicht") == False

def test_max_iterations():
    state.image_state.mood_board_iteration_count = 7
    decision = await design_henk.process(state)
    assert state.image_state.mood_board_approved == True
```

## Troubleshooting

### Problem: Moodboard wird nicht neu generiert

**Ursache:** Feedback wird nicht erkannt

**Lösung:** Prüfe `route_node()` Logging:
```python
logger.info(f"[RouteNode] Mood board feedback from user: {user_message}")
```

### Problem: CRM Lead wird nicht erstellt

**Ursache:** Pipedrive API Key fehlt oder ungültig

**Lösung:**
1. Prüfe `.env` für `PIPEDRIVE_API_KEY`
2. Teste API-Verbindung:
   ```python
   crm_tool = CRMTool()
   assert crm_tool.client is not None
   ```

### Problem: Iteration Counter springt nicht hoch

**Ursache:** State wird nicht gespeichert

**Lösung:** Prüfe in `design_henk.py`:
```python
state.image_state.mood_board_iteration_count += 1
```

## Zukünftige Erweiterungen

- [ ] A/B Testing: Mehrere Varianten gleichzeitig generieren
- [ ] Detailliertes Feedback-Parsing mit LLM
- [ ] Sentiment-Analyse für bessere Approval-Erkennung
- [ ] Image-to-Image Editing statt kompletter Re-Generation
- [ ] Verbesserte Prompt-Anpassung basierend auf User-Feedback

## Siehe auch

- [DALLE Integration](./DALLE_INTEGRATION.md)
- [RAG Setup](./RAG_SETUP.md)
- [Handoff Payloads](../models/handoff.py)
- [CRM Tool](../tools/crm_tool.py)
