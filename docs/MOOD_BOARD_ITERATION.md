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

## DALL-E Prompt Anpassung

### Wo der Prompt angepasst werden kann

**Hauptdatei:** `tools/dalle_tool.py`

**Methode:** `_build_mood_board_prompt()` (Zeilen 197-269)

Diese Methode baut den DALL-E Prompt für Moodboard-Generierung auf und enthält:

#### 1. Occasion-basierte Szenen (Zeile 217-224)
```python
occasion_scenes = {
    "Hochzeit": "elegant wedding reception venue with soft natural lighting, romantic garden setting",
    "Business": "modern executive office with floor-to-ceiling windows, professional corporate environment",
    "Gala": "luxury ballroom with chandeliers, sophisticated evening event atmosphere",
    "Casual": "contemporary urban lifestyle setting, natural daylight",
}
```

**Anpassung:** Neue Anlässe hinzufügen oder bestehende Szenen-Beschreibungen ändern.

#### 2. Prompt-Struktur (Zeile 256-266)
```python
prompt = f"""Create an elegant mood board for a bespoke men's suit in a {scene}.

FABRIC REFERENCE: Show suits made from {fabrics_text}.{design_details}

STYLE: {style}, sophisticated, high-quality menswear photography.

COMPOSITION: Professional fashion editorial style, clean layout, luxurious atmosphere.

SETTING: {occasion} - create the appropriate ambiance and backdrop.

NOTE: Leave bottom-right corner clear (for fabric swatches overlay)."""
```

**Anpassungen möglich:**
- Einleitungstext ändern ("Create an elegant mood board...")
- Stil-Direktiven anpassen ("sophisticated, high-quality menswear photography")
- Komposition-Anweisungen erweitern
- Zusätzliche Constraints hinzufügen (z.B. "focus on details", "show full suit")

#### 3. Design-Präferenzen Integration (Zeile 239-253)
```python
if design_preferences:
    revers = design_preferences.get("revers_type", "")
    shoulder = design_preferences.get("shoulder_padding", "")
    waistband = design_preferences.get("waistband_type", "")

    if revers or shoulder or waistband:
        design_details = "\n\nSUIT DESIGN:"
        if revers:
            design_details += f"\n- Lapel style: {revers}"
        if shoulder:
            design_details += f"\n- Shoulder: {shoulder}"
        if waistband:
            design_details += f"\n- Trouser waistband: {waistband}"
```

**Anpassung:** Zusätzliche Design-Details hinzufügen (z.B. Knopfanzahl, Taschenstil)

### Beispiel: Prompt für Business-Anzug

**Input:**
- Occasion: "Business"
- Fabric: "Dunkelblau, Uni, feine Wolle"
- Design: Spitzrevers, mittlere Schulter, Bundfalte
- Style: "elegant, modern"

**Generierter Prompt:**
```
Create an elegant mood board for a bespoke men's suit in a modern executive office with floor-to-ceiling windows, professional corporate environment.

FABRIC REFERENCE: Show suits made from Dunkelblau Uni fabric in feine Wolle.

SUIT DESIGN:
- Lapel style: Spitzrevers
- Shoulder: mittel
- Trouser waistband: Bundfalte

STYLE: elegant, modern, sophisticated, high-quality menswear photography.

COMPOSITION: Professional fashion editorial style, clean layout, luxurious atmosphere.

SETTING: Business - create the appropriate ambiance and backdrop.

NOTE: Leave bottom-right corner clear (for fabric swatches overlay).
```

### Tipps für Prompt-Optimierung

1. **Spezifität:** Je präziser die Beschreibung, desto besser das Ergebnis
2. **Keywords:** DALL-E reagiert gut auf "professional photography", "editorial style", "luxury"
3. **Constraints:** "Leave corner clear" verhindert überfüllte Kompositionen
4. **Fabric Details:** Farbe + Muster + Material = beste Ergebnisse
5. **Scene Setting:** Detaillierte Szenen-Beschreibungen verbessern Atmosphäre

## Zukünftige Erweiterungen

- [ ] A/B Testing: Mehrere Varianten gleichzeitig generieren
- [x] Detailliertes Feedback-Parsing mit Keyword-Erkennung (implementiert)
- [ ] Sentiment-Analyse für bessere Approval-Erkennung
- [ ] Image-to-Image Editing statt kompletter Re-Generation
- [x] Verbesserte Prompt-Anpassung basierend auf User-Feedback (implementiert)

## Siehe auch

- [DALLE Integration](./DALLE_INTEGRATION.md)
- [RAG Setup](./RAG_SETUP.md)
- [Handoff Payloads](../models/handoff.py)
- [CRM Tool](../tools/crm_tool.py)
