# HENK Style Assistant - Structured Output Implementation

**Datum:** 2025-12-19
**Branch:** `claude/henk-style-assistant-UswjE`
**Commit:** `60e3270`

---

## 🎯 **Problem Statement**

Die Moodbildgenerierung und User-Iterationen funktionierten nicht korrekt:

1. **PydanticAgent initialisierte nicht** → Leere `PatchDecision` Objekte
2. **User-Feedback wurde ignoriert** → Keine Extraktion von Design-Präferenzen
3. **Style Keywords hart codiert** → "modern" wurde zu "klassisch"
4. **Design-Präferenzen blieben statisch** → Immer die Mock-Werte
5. **DALLE Prompts unstrukturiert** → Inkonsistente Bildgenerierung

### Beispiel aus den Logs:

**User Input:** `"bitte nochmal als Einreiher und mit fallendem Revers"`

**Erwartet:**
```json
{
  "jacket_front": "single_breasted",
  "lapel_roll": "rolling"
}
```

**Tatsächlich:**
```json
{
  "patch": {"jacket_front": null, "lapel_roll": null},
  "changed_fields": []
}
```

---

## ✅ **Implementierte Lösung**

### 1. **design_patch_agent.py** - Moderne Pydantic-AI Integration

#### Änderungen:
- ✅ Ersetzt veraltete Pydantic-AI API (`@system_prompt` Decorator) durch moderne Syntax
- ✅ Dual-Backend Architektur:
  - **Primär:** Pydantic-AI Agent mit `result_type=PatchDecision`
  - **Fallback:** OpenAI Structured Outputs (beta API)
- ✅ Umfassendes System Prompt mit Synonym-Mapping

#### Neue Architektur:

```python
# Moderne Pydantic-AI Initialisierung
self.pydantic_agent = PydanticAgent(
    "openai:gpt-4o-mini",
    result_type=PatchDecision,
    system_prompt=self._build_system_prompt(),
)

# Extraktion
result = await self.pydantic_agent.run(user_message)
decision = result.data  # ← Bereits validiertes PatchDecision!
```

#### Fallback mit OpenAI Structured Outputs:

```python
completion = await self.openai_client.beta.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    response_format=PatchDecision,  # ← Direct Pydantic Model
)
decision = completion.choices[0].message.parsed
```

#### Synonym-Mapping (Auszug):

| User Input | Extrahiertes Feld | Wert |
|-----------|-------------------|------|
| "Einreiher" | `jacket_front` | `"single_breasted"` |
| "Zweireiter" | `jacket_front` | `"double_breasted"` |
| "fallendes Revers" | `lapel_roll` | `"rolling"` |
| "Spitzrevers" | `lapel_style` | `"peak"` |
| "ohne Schulterpolster" | `shoulder_padding` | `"none"` |
| "Bundfalte" | `trouser_front` | `"pleats"` |
| "ohne Weste" | `wants_vest` | `false` |

---

### 2. **design_henk.py** - LLM-basierte Feedback-Verarbeitung

#### Neue Methode: `_extract_style_keywords_from_feedback()`

Nutzt OpenAI zur intelligenten Keyword-Extraktion:

```python
async def _extract_style_keywords_from_feedback(self, feedback: str) -> list[str]:
    """
    Extract style keywords from German user feedback using LLM.

    Examples:
    - "modern, leicht, italienisch" → ["modern", "light", "italian"]
    - "ohne Futter ohne Polster" → ["unlined", "unpadded"]
    """
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": feedback}
        ],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    return data.get("keywords", [])
```

#### Verbesserte Patch-Anwendung:

```python
# Extract structured patches from feedback
patch_agent = DesignPatchAgent()
decision = await patch_agent.extract_patch_decision(
    user_message=state.image_state.mood_board_feedback,
    context="Designpräferenzen Update",
)

# Apply patches with confidence check
if decision.confidence > 0.5:
    updated_preferences = apply_design_preferences_patch(
        state.design_preferences, decision.patch
    )

    # Update state
    state.design_preferences = updated_preferences

    # Update wants_vest in root state
    if decision.patch.wants_vest is not None:
        state.wants_vest = decision.patch.wants_vest

    # Update design_prefs dict for DALLE
    design_prefs.update({
        "jacket_front": state.design_preferences.jacket_front,
        "lapel_style": state.design_preferences.lapel_style,
        "lapel_roll": state.design_preferences.lapel_roll,
        "trouser_front": state.design_preferences.trouser_front,
    })
```

#### Detailliertes Logging:

```python
logger.info(
    "[DesignHenk] 🔄 Updated %s: %s → %s",
    field_name,
    old_value,
    new_value,
)

logger.info(
    "[DesignHenk] ✅ Applied %d fields from PatchDecision: %s",
    len(applied_fields),
    applied_fields,
)
```

---

### 3. **dalle_tool.py** - Strukturierte Design-Spezifikationen

#### Erweiterte Design-Detail-Extraktion:

```python
# Jacket construction
if jacket_front == "single_breasted":
    design_details_parts.append("Single-breasted jacket (one row of buttons)")
elif jacket_front == "double_breasted":
    design_details_parts.append("Double-breasted jacket (two rows of buttons)")

# Lapel styling
if lapel_style == "peak":
    design_details_parts.append("peak lapels (pointed upward)")
if lapel_roll == "rolling":
    design_details_parts.append("with soft rolling/falling lapels")

# Shoulder construction
shoulder_mapping = {
    "none": "unstructured soft shoulders (spalla camicia, no padding)",
    "light": "lightly padded shoulders",
    "medium": "medium shoulder padding",
    "structured": "structured shoulders with strong padding"
}
```

#### Verbesserter DALL-E Prompt:

**Vorher:**
```
STYLE: klassisch, User feedback: bitte nochmal als Einreiher und mit fallendem Revers
```

**Nachher:**
```
SUIT DESIGN SPECIFICATIONS:
- Single-breasted jacket (one row of buttons)
- peak lapels (pointed upward) with soft rolling/falling lapels
- unstructured soft shoulders (spalla camicia, no padding)
- pleated front trousers

CRITICAL COMPOSITION: Show TWO-PIECE suit ONLY (jacket and trousers). NO vest/waistcoat visible.
```

---

## 📊 **Erwartete Verbesserungen**

### Test Case 1: Einreiher mit fallendem Revers

**Input:** `"bitte nochmal als Einreiher und mit fallendem Revers"`

**Vorher:**
- PatchDecision: `{}`
- Design-Präferenzen: Keine Änderungen
- DALLE Prompt: Generischer Text

**Nachher:**
- PatchDecision: `{"jacket_front": "single_breasted", "lapel_roll": "rolling"}` (confidence: 0.95)
- Design-Präferenzen: `jacket_front="single_breasted"`, `lapel_roll="rolling"`
- DALLE Prompt: "Single-breasted jacket (one row of buttons) with soft rolling/falling lapels"

---

### Test Case 2: Italienischer Stil ohne Polster

**Input:** `"modern, leicht, italienisch, ohne Futter ohne Polster, mit aufgesetzten Taschen"`

**Vorher:**
- Style Keywords: `["klassisch"]` (hart codiert)
- Design-Präferenzen: Keine Änderungen

**Nachher:**
- Style Keywords: `["modern", "light", "italian", "unlined", "unpadded", "patch pockets"]`
- Design-Präferenzen: `shoulder_padding="none"`, `notes_normalized="modern italienisch leicht ohne Futter"`
- DALLE Prompt: "unstructured soft shoulders (spalla camicia, no padding)"

---

### Test Case 3: Ohne Weste

**Input:** `"Nochmal ohne Weste bitte"`

**Vorher:**
- wants_vest: `None`
- DALLE Prompt: Keine Westen-Instruktion

**Nachher:**
- wants_vest: `false`
- DALLE Prompt: "CRITICAL COMPOSITION: Show TWO-PIECE suit ONLY (jacket and trousers). NO vest/waistcoat visible."

---

## 🏗️ **Architektur-Übersicht**

```
┌─────────────────────────────────────────────────────────────┐
│                       USER FEEDBACK                         │
│   "bitte nochmal als Einreiher und mit fallendem Revers"   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              DESIGN_PATCH_AGENT.PY                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Pydantic-AI Agent (Primary)                        │  │
│  │    - Model: openai:gpt-4o-mini                        │  │
│  │    - result_type: PatchDecision                       │  │
│  │    - System Prompt: Synonym Mapping                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │ (if fails)                            │
│                      ▼                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. OpenAI Structured Outputs (Fallback)               │  │
│  │    - Model: gpt-4o-2024-08-06                         │  │
│  │    - response_format: PatchDecision                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │                                        │
│                      ▼                                        │
│              PatchDecision                                   │
│  {                                                           │
│    "patch": {                                                │
│      "jacket_front": "single_breasted",                      │
│      "lapel_roll": "rolling"                                 │
│    },                                                        │
│    "confidence": 0.95,                                       │
│    "changed_fields": ["jacket_front", "lapel_roll"]         │
│  }                                                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 DESIGN_HENK.PY                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Apply Patches to DesignPreferences                 │  │
│  │    apply_design_preferences_patch()                   │  │
│  │    → state.design_preferences.jacket_front = "single" │  │
│  │    → state.design_preferences.lapel_roll = "rolling"  │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. Extract Style Keywords from Feedback              │  │
│  │    _extract_style_keywords_from_feedback()           │  │
│  │    → ["modern", "italian", "light"]                  │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 3. Merge Keywords                                     │  │
│  │    style_keywords.extend(feedback_keywords)          │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │                                        │
│                      ▼                                        │
│              design_prefs Dict                               │
│  {                                                           │
│    "jacket_front": "single_breasted",                        │
│    "lapel_roll": "rolling",                                  │
│    "revers_type": "Spitzrevers",                             │
│    "shoulder_padding": "none"                                │
│  }                                                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  DALLE_TOOL.PY                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Build Structured Design Details                    │  │
│  │    - "Single-breasted jacket (one row of buttons)"    │  │
│  │    - "with soft rolling/falling lapels"               │  │
│  │    - "unstructured soft shoulders (spalla camicia)"   │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │                                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 2. Generate DALL-E Prompt                             │  │
│  │    SUIT DESIGN SPECIFICATIONS:                        │  │
│  │    - Single-breasted jacket (one row of buttons)      │  │
│  │    - peak lapels with soft rolling/falling lapels     │  │
│  │    - unstructured soft shoulders                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                      │                                        │
│                      ▼                                        │
│              DALL-E 3 API                                    │
│  → Mood Board Image (with precise design specifications)    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 **Testing**

### Testskript: `test_patch_extraction.py`

Zum Testen der Patch-Extraktion:

```bash
python test_patch_extraction.py
```

**Test Cases:**
1. ✅ Einreiher mit fallendem Revers
2. ✅ Ohne Weste
3. ✅ Italienischer Stil ohne Polster
4. ✅ Spitzrevers mit Bundfalte
5. ✅ Zweireihig mit Weste

---

## 📝 **Nächste Schritte**

1. **Integration Testing:** Vollständigen Flow mit Flask App testen
2. **Monitoring:** Logs überprüfen für Confidence-Scores und changed_fields
3. **Edge Cases:** Testen mit unklaren/ambiguen User-Inputs
4. **Performance:** Latenz-Messung für Pydantic-AI vs. Structured Outputs

---

## 🎓 **Learnings & Best Practices**

### Pydantic-AI
- ✅ Moderne API nutzt `result_type` statt Generics
- ✅ `system_prompt` als String-Parameter (nicht Decorator)
- ✅ `result.data` enthält bereits validiertes Pydantic-Objekt

### OpenAI Structured Outputs
- ✅ Benötigt `gpt-4o-2024-08-06` Modell
- ✅ `beta.chat.completions.parse()` für direkte Pydantic-Validierung
- ✅ Robuster Fallback wenn Pydantic-AI nicht verfügbar

### LangGraph State Management
- ✅ Patches nur bei `confidence > 0.5` anwenden
- ✅ Alle Änderungen detailliert loggen
- ✅ `changed_fields[]` für Tracking verwenden

### DALL-E Prompting
- ✅ Klare, strukturierte Spezifikationen statt rohe User-Strings
- ✅ Explizite Instruktionen für kritische Details (z.B. Weste)
- ✅ Mapping von technischen Begriffen zu verständlichen Beschreibungen

---

**Commit:** `60e3270`
**Branch:** `claude/henk-style-assistant-UswjE`
**Status:** ✅ Ready for Testing
