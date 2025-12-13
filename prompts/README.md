# LASERHENK DALL-E Prompt Templates

Dieser Ordner enthält Prompt-Templates für die DALL-E Bildgenerierung.

## Struktur

### Haupttemplates (`*.txt`)
- `outfit_visualization.txt` - Fotorealistische Anzug-Darstellung
- `mood_board.txt` - Stil-Inspiration und Farbkombinationen
- `detail_focus.txt` - Close-ups von Anzug-Details
- `fabric_texture.txt` - Stoff-Textur Visualisierung
- `brand_guidelines.txt` - LASERHENK Brand Identity
- `default.txt` - Fallback Template

### Examples Ordner (`examples/`)
Platzhalter für:
- Beispiel-Fotos
- Referenz-Outfits
- Farb-Paletten
- Stil-Referenzen

## Verwendung im Code

```python
from tools.dalle_tool import get_dalle_tool

dalle = get_dalle_tool()

# Template laden
prompt = dalle.build_prompt(
    prompt_type="outfit_visualization",
    fabric_data={"colors": ["navy", "burgundy"], "patterns": ["herringbone"]},
    design_preferences={"revers_type": "peak_lapel", "jacket_form": "slim_fit"},
    style_keywords=["elegant", "modern", "business"]
)

# Bild generieren
response = await dalle.generate_outfit_visualization(
    fabric_data=fabric_data,
    design_preferences=design_prefs,
    style_keywords=["elegant"],
    session_id=session_id
)
```

## Template-Erweiterung

Neue Templates hinzufügen:
1. Erstelle `<name>.txt` in diesem Ordner
2. Verwende `prompt_type="<name>"` in `build_prompt()`
3. Folge den Brand Guidelines für Konsistenz

## Brand Guidelines

Die `brand_guidelines.txt` wird automatisch an jeden Prompt angehängt.
Änderungen hier beeinflussen alle generierten Bilder.

**Wichtig**: Brand Guidelines nicht löschen oder fundamental ändern ohne Abstimmung!

## Beispiele hinzufügen

Lege Beispiel-Bilder im `examples/` Ordner ab:
- `examples/outfit_examples/` - Referenz-Outfits
- `examples/fabrics/` - Stoff-Fotos
- `examples/details/` - Detail-Aufnahmen
- `examples/moodboards/` - Mood Board Inspirationen

Diese Bilder dienen als visuelle Referenz für das Team und können
später auch für Fine-Tuning oder CLIP-basierte Suche verwendet werden.
