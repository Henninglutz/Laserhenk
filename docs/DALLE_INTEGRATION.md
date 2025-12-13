# DALL-E Integration - Bildgenerierung für LASERHENK

## Übersicht

Die DALL-E Integration ermöglicht die automatische Generierung von:
- **Mood Boards** (HENK1): Frühe visuelle Inspiration basierend auf Kundenvorstellungen
- **Outfit-Visualisierungen** (Design Henk): Fotorealistische Darstellungen des geplanten Anzugs

## Architektur

### Komponenten

1. **DALL-E Tool** (`tools/dalle_tool.py`)
   - Wrapper für OpenAI DALL-E 3 API
   - Prompt-Engineering mit Templates
   - Lokale Bildspeicherung
   - High-level Methoden für verschiedene Bildtypen

2. **Prompt Templates** (`prompts/*.txt`)
   - `outfit_visualization.txt` - Fotorealistische Anzug-Darstellung
   - `mood_board.txt` - Stil-Inspiration
   - `detail_focus.txt` - Close-ups von Details
   - `fabric_texture.txt` - Stoff-Texturen
   - `brand_guidelines.txt` - LASERHENK Brand Identity (wird allen Prompts hinzugefügt)

3. **Agent Integration**
   - **HENK1**: Mood Board nach 3-4 Gesprächsrunden
   - **Design Henk**: Outfit-Visualisierung nach Design-Details Sammlung

4. **Workflow Integration** (`workflow/nodes.py`)
   - Neue Actions: `generate_mood_board`, `generate_image`
   - Tool Dispatcher für DALL-E Routing
   - Conditional Edges für Image Generation Flow

5. **Storage Management** (`tools/image_storage.py`)
   - Lokale Speicherung in `generated_images/`
   - Session-Archivierung in `docs/sessions/<session_id>/`
   - Image Approval Tracking
   - Optional: CRM Upload (Pipedrive)

## Ablauf

### HENK1 - Mood Board Generierung

```
1. User: "Hallo"
2. HENK1: "Moin! 👋 Planst du einen besonderen Anlass?"
3. User: "Ja, eine Hochzeit im Sommer"
4. HENK1: "Welche Farben schweben dir vor?"
5. User: "Helles Blau und Beige"

   ⚡ TRIGGER: Mood Board Generation (Anlass + Farben vorhanden)

6. HENK1: "Moment, ich erstelle ein Mood Board zur Inspiration! 🎨"
7. [DALL-E generiert Mood Board]
8. HENK1: "🎨 Dein Mood Board ist fertig! Was denkst du?"
9. [Bild wird im Browser angezeigt]
```

### Design Henk - Outfit-Visualisierung

```
1. User: [kommt von HENK1 mit Stoffauswahl]
2. Design Henk: "Welchen Revers-Stil bevorzugst du?"
3. User: "Spitzrevers"
4. Design Henk: "Wie ausgeprägt soll die Schulter sein?"
5. User: "Leichte Polsterung"

   ⚡ TRIGGER: Outfit Visualization (Design-Details komplett)

6. Design Henk: "Generiere dein Outfit-Moodbild..."
7. [DALL-E generiert fotorealistische Outfit-Darstellung]
8. Design Henk: "✨ Dein Outfit-Entwurf ist fertig!"
9. [Bild wird im Browser angezeigt]
10. User: "Gefällt mir!"

    ⚡ TRIGGER: Image Approval & Archivierung
```

## API Endpoints

### 1. Chat Endpoint (mit Bild-Support)

```http
POST /api/chat
Content-Type: application/json

{
  "message": "Helles Blau und Beige wären schön",
  "session_id": "abc-123"
}
```

**Response:**
```json
{
  "reply": "🎨 Dein Mood Board ist fertig!...",
  "session_id": "abc-123",
  "stage": "henk1",
  "image_url": "https://oaidalleapiprodscus.blob.core.windows.net/...",
  "messages": [...]
}
```

### 2. Image Approval Endpoint

```http
POST /api/session/{session_id}/approve-image
Content-Type: application/json

{
  "image_url": "https://...",
  "image_type": "outfit_visualization"
}
```

**Response:**
```json
{
  "success": true,
  "approved_image": "https://...",
  "message": "Bild wurde bestätigt und archiviert"
}
```

## Frontend Integration

Das Frontend (`templates/static/app.js`) zeigt Bilder automatisch an:

```javascript
// Bild wird automatisch angezeigt wenn image_url in Response
const imageUrl = data.image_url || null;
addMessage("assistant", reply, imageUrl);
```

**HTML Rendering:**
```html
<div class="msg assistant">
  <div class="bubble">
    Dein Mood Board ist fertig!
    <img src="https://..."
         alt="Moodboard"
         style="max-width:100%; margin-top:10px; border-radius:8px;">
  </div>
</div>
```

## Konfiguration

### Environment Variables

```bash
# .env
OPENAI_API_KEY=sk-...           # Für DALL-E 3 API
ENABLE_DALLE=true               # DALL-E aktivieren/deaktivieren
```

### Prompt Engineering

**Template bearbeiten:**
```bash
# prompts/outfit_visualization.txt bearbeiten
vim prompts/outfit_visualization.txt
```

**Neues Template hinzufügen:**
```bash
# Neues Template erstellen
echo "Dein Prompt..." > prompts/my_custom_prompt.txt

# Im Code verwenden
dalle.build_prompt(
    prompt_type="my_custom_prompt",
    fabric_data=...,
    design_preferences=...
)
```

**Brand Guidelines anpassen:**
```bash
# prompts/brand_guidelines.txt bearbeiten
# WICHTIG: Wird allen Prompts automatisch hinzugefügt!
vim prompts/brand_guidelines.txt
```

## State Management

### SessionState Attributes

```python
class SessionState:
    # DALL-E Related
    mood_image_url: Optional[str]                    # Aktuell angezeigtes Bild
    henk1_mood_board_shown: bool                     # Flag: Mood Board gezeigt
    image_generation_history: list[dict]             # Alle generierten Bilder

    # Design Preferences
    design_preferences.approved_image: Optional[str] # User-bestätigtes Bild
```

### Image Generation History Format

```python
{
    "url": "https://...",
    "type": "mood_board" | "outfit_visualization",
    "timestamp": "2025-12-12T14:30:00",
    "approved": False,
    "approved_at": "2025-12-12T14:35:00"  # Nur wenn approved=True
}
```

## Speicherstrategie

### 1. Lokale Speicherung

```
generated_images/
├── abc123_20251212_143000.png    # Temp. Speicherung aller Bilder
├── abc123_20251212_143100.png
└── ...
```

**Auto-Cleanup:**
```python
from tools.image_storage import get_storage_manager

storage = get_storage_manager()

# Lösche Bilder älter als 30 Tage (behalte approved)
await storage.cleanup_old_images(max_age_days=30, keep_approved=True)
```

### 2. Session Archivierung

```
docs/sessions/
└── abc-123/
    ├── approved_20251212_143500.png  # User-bestätigte Bilder
    └── ...
```

### 3. Image Approval

```python
from tools.image_storage import get_storage_manager

storage = get_storage_manager()

# Bild als approved markieren
await storage.approve_image(
    session_state=state,
    image_url=image_url,
    image_type="outfit_visualization"
)

# Automatisch in docs/sessions/<session_id>/ archiviert
```

### 4. CRM Integration (Optional)

```python
# TODO: Pipedrive API Integration
await storage.upload_to_crm(
    crm_lead_id=state.customer.crm_lead_id,
    image_url=image_url,
    description="Approved Outfit Design"
)
```

## Conditional Edges

### HENK1 Flow

```
[User Input]
    ↓
[HENK1 Agent]
    ↓
[Check: should_generate_mood_board()?]
    ├─ Ja → [Action: generate_mood_board]
    │         ↓
    │       [Operator]
    │         ↓
    │       [Tools Dispatcher: dalle_mood_board]
    │         ↓
    │       [DALL-E Tool: generate_mood_board()]
    │         ↓
    │       [Update State: mood_image_url, history]
    │         ↓
    │       [Return to HENK1]
    │         ↓
    │       [Weiteres Gespräch]
    │
    └─ Nein → [Check: should_query_rag()?]
               ├─ Ja → [RAG Tool]
               └─ Nein → [Weiteres Gespräch]
```

### Design Henk Flow

```
[Design Preferences gesammelt]
    ↓
[Design Henk Agent]
    ↓
[Check: mood_image_url vorhanden?]
    ├─ Nein → [Action: generate_image]
    │           ↓
    │         [Operator]
    │           ↓
    │         [Tools Dispatcher: dalle_outfit]
    │           ↓
    │         [DALL-E Tool: generate_outfit_visualization()]
    │           ↓
    │         [Update State: mood_image_url, history]
    │           ↓
    │         [Return to Design Henk]
    │           ↓
    │         [CRM Lead erstellen]
    │
    └─ Ja → [CRM Lead erstellen]
```

## Best Practices

### Prompt Engineering

1. **Spezifisch sein**: Je detaillierter der Prompt, desto besser das Ergebnis
2. **Brand Guidelines einhalten**: Automatisch in jedem Prompt enthalten
3. **Konsistenz**: Ähnliche Prompts für ähnliche Bildtypen verwenden
4. **Testen**: Verschiedene Prompt-Variationen testen

### Performance

1. **Caching**: DALL-E Calls sind teuer (€0.04-0.08 pro Bild)
2. **Deduplication**: Nicht mehrfach für gleiche Params generieren
3. **Async**: Immer async/await verwenden
4. **Error Handling**: Graceful Degradation bei API-Fehlern

### User Experience

1. **Feedback**: User informieren während Generierung
2. **Approval**: User bestätigen lassen vor Archivierung
3. **Iteration**: User soll Änderungen anfordern können
4. **Fallback**: System muss ohne Bilder funktionieren

## Debugging

### Logs aktivieren

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("tools.dalle_tool")
logger.setLevel(logging.DEBUG)
```

### Typische Probleme

**1. DALL-E API Fehler**
```python
# Fehler: "DALL-E ist deaktiviert"
# Lösung: ENABLE_DALLE=true in .env setzen

# Fehler: "Invalid API Key"
# Lösung: OPENAI_API_KEY in .env prüfen

# Fehler: "Content Policy Violation"
# Lösung: Prompt anpassen, keine unangemessenen Inhalte
```

**2. Bilder werden nicht angezeigt**
```javascript
// Frontend Konsole prüfen:
console.log("Image URL:", data.image_url);

// Backend Logs prüfen:
[DALLE_MoodBoard] Success: https://...
```

**3. Speicherung funktioniert nicht**
```bash
# Permissions prüfen
ls -la generated_images/
ls -la docs/sessions/

# Ordner manuell erstellen wenn nötig
mkdir -p generated_images docs/sessions
chmod 755 generated_images docs/sessions
```

## Testing

### Unit Tests (TODO)

```python
import pytest
from tools.dalle_tool import DALLETool

async def test_mood_board_generation():
    dalle = DALLETool()
    response = await dalle.generate_mood_board(
        style_keywords=["elegant"],
        colors=["navy", "beige"],
        occasion="Hochzeit",
    )
    assert response.success
    assert response.image_url is not None
```

### Integration Test

```bash
# 1. Server starten
python run.py

# 2. Browser öffnen
# http://localhost:8000

# 3. Test-Konversation:
# User: "Hallo"
# User: "Ich habe eine Hochzeit"
# User: "Navy und Beige gefallen mir"
# [Mood Board sollte erscheinen]
```

## Kosten

**DALL-E 3 Preise (Stand 2025):**
- Standard Quality (1024x1024): $0.040 pro Bild
- HD Quality (1024x1024): $0.080 pro Bild

**Typische Session:**
- 1x Mood Board (HENK1): $0.040
- 1x Outfit Visualization (Design Henk): $0.080
- **Total: ~$0.12 pro Kunde**

**Kostenoptimierung:**
- Mood Boards nur wenn sinnvoll (nicht bei jeder Session)
- Deduplication (gleiche Params = gleiches Bild)
- Standard Quality für Mood Boards
- HD Quality nur für finale Outfit-Visualisierungen

## Roadmap

### Geplante Features

- [ ] **Re-Generation**: User kann Änderungswünsche äußern
- [ ] **Style Transfer**: Bestehende Bilder als Referenz
- [ ] **Detail Views**: Separate Generierung von Details (Revers, Knöpfe, etc.)
- [ ] **Pipedrive Integration**: Auto-Upload zu CRM
- [ ] **Image Variants**: Mehrere Varianten zur Auswahl
- [ ] **DALL-E Edit API**: Bestehende Bilder bearbeiten
- [ ] **Image Feedback Loop**: User-Feedback für Prompt-Verbesserung

## Weitere Informationen

- **DALL-E 3 API Docs**: https://platform.openai.com/docs/guides/images
- **Prompt Engineering Guide**: https://platform.openai.com/docs/guides/prompt-engineering
- **Brand Guidelines**: `prompts/brand_guidelines.txt`
