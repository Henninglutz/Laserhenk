# HENK1 Flow Korrektur - DALL-E NACH RAG

## Status: ✅ Bestätigt & Dokumentiert

## Problem (Alte Implementation):
```
HENK1: Sammelt Wünsche → Mood Board (allgemein) → RAG (Stoffe-Text) → Design Henk
```
- Mood Board zu früh (ohne konkrete Stoffe)
- Nur abstrakte Farben/Stile
- RAG zeigt nur Text-Liste
- Kunde kann nicht visuell vergleichen

## Lösung (Neue Implementation):
```
HENK1: Sammelt Wünsche → RAG (konkrete Stoffe-Text) → Mood Board MIT Stoffen → Design Henk
```
- RAG liefert konkrete Stoffempfehlungen
- Mood Board zeigt 2 Stoff-Varianten aus RAG
- Kulisse/Hintergrund basiert auf Anlass
- Kunde kann visuell vergleichen und entscheiden

## Detaillierter Flow:

### 1. Bedarfsermittlung (HENK1)
```
User: "Hallo"
HENK1: "Moin! Planst du einen besonderen Anlass?"
User: "Ja, Hochzeit im Sommer"
HENK1: "Welche Farben schweben dir vor?"
User: "Helles Blau und Beige"
HENK1: "Klassisch oder modern?"
User: "Klassisch. Zeig mir Stoffe!"
```

### 2. RAG Query (HENK1 triggert)
```
[RAG Suche: blau, beige, klassisch, Hochzeit, Sommer]

RAG Ergebnisse:
1. Navy Blau Fischgrat, 280g/m², Schurwolle, €1.850
2. Hell Beige Köper, 260g/m², Baumwolle-Leinen, €1.620
3. Mittelblau Uni, 270g/m², Schurwolle, €1.750
...
```

### 3. Text-Liste an User (HENK1)
```
HENK1: "Hier sind meine Top-Empfehlungen für deine Hochzeit:

**1. Navy Blau Fischgrat**
   📦 Material: Schurwolle
   🎨 Farbe: Navy Blau
   ✨ Muster: Fischgrat
   ⚖️ Gewicht: 280g/m²
   💯 Perfekt für klassische Hochzeiten

**2. Hell Beige Köper**
   📦 Material: Baumwolle-Leinen
   🎨 Farbe: Hell Beige
   ✨ Muster: Köper
   ⚖️ Gewicht: 260g/m²
   💯 Sehr gut für Sommerhochzeiten

[...]

Lass mich dir zeigen, wie diese Stoffe in deinem Hochzeits-Setting aussehen würden!"
```

### 4. Mood Board Generation (HENK1 triggert)
```
[DALL-E generiert Mood Board]

Prompt:
- 2 Anzug-Varianten (Navy Fischgrat vs. Beige Köper)
- Hochzeits-Kulisse (Kirche, Festsaal, Garten)
- Nebeneinander zum Vergleich
- Fotorealistisch
- Im Kontext (Hochzeitsgast)

Ergebnis: Bild mit beiden Stoffen im Hochzeits-Setting
```

### 5. Mood Board Anzeige (HENK1)
```
HENK1: "🎨 So könnten die Stoffe in deinem Hochzeits-Setting aussehen!"

[Bild wird im Browser angezeigt]

HENK1: "Links der Navy Fischgrat, rechts der Beige Köper.
Welcher gefällt dir besser für die Hochzeit?"
```

### 6. User Auswahl & Übergabe
```
User: "Der Navy gefällt mir sehr gut!"

HENK1: "Perfekt! Lass uns die Details mit Design Henk besprechen..."

→ Übergabe an Design Henk mit:
  - Ausgewählter Stoff: Navy Blau Fischgrat
  - Anlass: Hochzeit
  - Stil: Klassisch
  - Mood Board URL
```

## Implementierungs-Details:

### Neue Komponenten:

1. **Prompt Template**: `prompts/mood_board_with_fabrics.txt`
   - Zeigt 2 konkrete Stoffe aus RAG
   - Anlass-basierte Kulisse
   - Side-by-Side Vergleich

2. **DALL-E Methode**: `generate_mood_board_with_fabrics()`
   - Nimmt RAG-Ergebnisse als Input
   - Wählt Top 2 Stoffe
   - Extrahiert Anlass für Kulisse
   - Generiert Vergleichs-Bild

3. **Workflow Action**: `generate_mood_board_with_fabrics`
   - Wird NACH RAG getriggert
   - Nutzt RAG Context
   - Zeigt 2 Stoff-Varianten

### Vorteile:

✅ **Konkret statt abstrakt** - Echte Stoffe statt Farbmuster
✅ **Visueller Vergleich** - Kunde sieht Unterschied direkt
✅ **Kontext-bezogen** - Kulisse passt zum Anlass
✅ **Kaufentscheidung** - Kunde kann informiert wählen
✅ **Seamless Flow** - Text → Bild → Auswahl

### State Flow:

```python
# VORHER (falsch):
state.henk1_mood_board_shown = True  # Zu früh, vor RAG
state.henk1_rag_queried = False

# NACHHER (korrekt):
state.henk1_rag_queried = True  # Erst RAG
state.rag_context = { "fabrics": [...] }  # RAG Daten
state.henk1_mood_board_shown = True  # Dann Mood Board MIT Stoffen
```

## Beispiel Bild-Prompt:

```
Erstelle ein elegantes Mood Board für einen maßgeschneiderten Hochzeitsanzug.

STOFF-VARIANTEN (aus Datenbank):
1. Navy Blau Fischgrat, 280g/m², Schurwolle
   - Klassisches Muster
   - Elegante Textur
   - Traditionell für Hochzeiten

2. Hell Beige Köper, 260g/m², Baumwolle-Leinen
   - Sommerlicher Stoff
   - Leicht und atmungsaktiv
   - Modern für Sommerhochzeiten

SETTING/KULISSE:
- Hochzeit im Sommer
- Elegante Kirche oder Festsaal
- Natürliches Tageslicht
- Festliche Atmosphäre

KOMPOSITION:
- Split-Screen: Links Navy, Rechts Beige
- Beide Anzüge in gleicher Pose/Perspektive
- Im Hochzeits-Kontext (Kirche/Festsaal im Hintergrund)
- Fotorealistisch
- Direkter Vergleich ermöglichen

MARKE: LASERHENK
- Zeitlos-elegant
- Hochwertig
- Premium-Qualität

[DALL-E 3 generiert...]
```

## Ergebnis:

Kunde erhält:
1. ✅ **Text-Liste** mit technischen Daten (Material, Gewicht, Preis)
2. ✅ **Visuelles Mood Board** mit 2 Stoffen im Anlass-Kontext
3. ✅ **Vergleichbarkeit** für informierte Entscheidung
4. ✅ **Kontext-Verständnis** wie es am Anlass aussieht

→ **Bessere User Experience**
→ **Höhere Conversion Rate**
→ **Klarere Entscheidungsgrundlage**
