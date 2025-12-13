# TODO für Morgen - LASERHENK System Fix
**Datum:** 14. Dezember 2025
**Status:** KRITISCH - Bilder werden nicht angezeigt
**Zeit verfügbar:** WENIG ⏰

---

## 🔴 PRIORITÄT 1: Bilder zum Laufen bringen (30-60 Min)

### Problem
- RAG findet Stoffe ✅
- Text wird angezeigt ✅
- **ABER: Keine Bilder werden angezeigt** ❌
- API Response enthält **KEIN `fabric_images` Feld**

### Root Cause
Nach RAG-Ausführung wird `show_fabric_images` **NIE** getriggert!

**Workflow-Flow aktuell:**
```
User: "zeig stoffe"
  ↓
Supervisor → RAG Tool (findet Stoffe)
  ↓
"Moment, ich zeige dir die Stoffe visuell! 🎨"
  ↓
❌ STOPP! Workflow wartet auf User Input
  ↓
User: "ja visuell"
  ↓
Supervisor → RAG NOCHMAL (Loop!)
```

**Workflow-Flow SOLLTE sein:**
```
User: "zeig stoffe"
  ↓
Supervisor → HENK1 (triggers query_rag)
  ↓
RAG Tool (findet Stoffe, speichert in rag_context)
  ↓
Return to HENK1 (awaiting_user_input=False)
  ↓
HENK1: Checks henk1_rag_queried=True → triggers show_fabric_images
  ↓
show_fabric_images (liest rag_context, baut fabric_images)
  ↓
API sendet fabric_images an Frontend
  ↓
Frontend zeigt Bilder! ✅
```

### Quick Fixes (IN REIHENFOLGE)

#### 1. Prüfe ob HENK1 nach RAG aufgerufen wird (5 Min)

```bash
cd ~/Laserhenk
git pull
python run_flask.py

# Im Browser teste: "zeig blaue stoffe"
# Schaue im Terminal nach:
```

**Erwartete Logs:**
```
[ToolsDispatcher] Executing tool='rag_tool'
[ToolsDispatcher] current_agent='henk1' (will return here)
[RAGTool] Executing fabric search...
[ToolsDispatcher] Returning to agent 'henk1' after tool execution
[HENK1] RAG queried, now showing fabric images  ← DIES MUSS KOMMEN!
[ShowFabricImages] Displaying real fabric images...
```

**Falls "HENK1" Log FEHLT:**
- Problem: Workflow kehrt nicht zu HENK1 zurück
- Fix: In `workflow/nodes.py` Zeile 599-617 prüfen

#### 2. Falls HENK1 aufgerufen wird, aber show_fabric_images nicht (10 Min)

**Prüfe:**
```python
# agents/henk1.py Zeile 114-140
# Bedingung: state.henk1_rag_queried and not state.henk1_mood_board_shown
```

**Debug:**
```python
# In henk1.py nach Zeile 109 hinzufügen:
print(f"=== RAG Context: {getattr(state, 'rag_context', {})}")
print(f"=== Fabrics in context: {len(getattr(state, 'rag_context', {}).get('fabrics', []))}")
```

#### 3. Falls show_fabric_images aufgerufen wird, aber keine Bilder sendet (15 Min)

**Prüfe Bild-URLs in Datenbank:**
```bash
# Falls Docker läuft:
docker exec -it laserhenk_postgres psql -U henk_user -d henk_rag -c \
  "SELECT fabric_code, additional_metadata->>'image_url' FROM fabrics LIMIT 5;"
```

**Problem:** Bilder haben wahrscheinlich **kaputte URLs** oder **NULL**

**Quick Fix:** Platzhalter-Bilder nutzen

```python
# In workflow/nodes.py _execute_show_fabric_images:
# Falls image_url None ist, nutze Platzhalter:
image_url = fabric.get("image_url") or "https://via.placeholder.com/400x300?text=Fabric"
```

---

## 🟡 PRIORITÄT 2: SupervisorAgent stabilisieren (15 Min)

### Problem
SupervisorAgent gibt manchmal String statt SupervisorDecision zurück.

### Status
✅ Fix committed (JSON String Parsing)

### Test
```bash
git pull
python run_flask.py

# Teste mehrere Anfragen, schaue ob Fehler weg sind:
# "zeig stoffe"
# "welcher passt besser"
# "ich brauche einen anzug"
```

**Erwartete Logs:**
```
[SupervisorAgent] Successfully parsed JSON string to SupervisorDecision
```

**Falls immer noch Fehler:**
- Supervisor durch HENK1 direkt ersetzen (Fallback ohne Supervisor)

---

## 🟢 PRIORITÄT 3: .env Zeile 108 Fix (5 Min)

### Problem
```
python-dotenv could not parse statement starting at line 108
```

### Quick Fix
```bash
cd ~/Laserhenk

# Zeige Zeile 108:
sed -n '108p' .env

# Falls leer oder kaputt:
# Öffne .env, lösche Zeile 108
# Oder ersetze durch leeren Kommentar:
sed -i '' '108s/.*/#/' .env  # Mac
```

---

## 📋 OPTIONAL (falls Zeit über): Datenbank-Bilder reparieren

### Falls Datenbank läuft und Bilder fehlen

1. **Prüfe welche Fabrics keine Bilder haben:**
```sql
SELECT fabric_code, name, additional_metadata
FROM fabrics
WHERE additional_metadata->>'image_url' IS NULL
LIMIT 10;
```

2. **Füge Platzhalter-URLs hinzu:**
```sql
UPDATE fabrics
SET additional_metadata = jsonb_set(
    COALESCE(additional_metadata, '{}'::jsonb),
    '{image_url}',
    '"https://via.placeholder.com/400x300?text=Fabric"'
)
WHERE additional_metadata->>'image_url' IS NULL;
```

---

## 🎯 ERFOLGS-KRITERIEN für Morgen

**Minimum Viable Product (MUSS funktionieren):**
1. ✅ User: "zeig blaue stoffe"
2. ✅ System findet Stoffe via RAG
3. ✅ System zeigt 2-3 **BILDER** von Stoffen
4. ✅ User kann Bilder sehen im Browser
5. ✅ Keine Fehler im Terminal

**Wenn das funktioniert: FERTIG für morgen!** 🎉

---

## 📊 Was heute funktioniert

✅ Flask läuft
✅ OpenAI API Key funktioniert
✅ PostgreSQL connected (Daten vorhanden!)
✅ RAG findet Stoffe (404.599/5, 10C4017, 10C4018)
✅ Keine Shirts mehr (Filter funktioniert)
✅ SupervisorAgent Validation Errors gefixt
✅ Workflow-Routing verbessert

❌ **Bilder werden nicht angezeigt** ← MORGEN FIXEN!

---

## 🔧 Commits heute

```
9a60918 - Fix: SupervisorAgent JSON string parsing to SupervisorDecision
1bb935e - Fix: Increase SupervisorAgent reasoning max_length to 500 chars
7a9ff7b - Add debug logging for tools_dispatcher current_agent routing
674db20 - Add PostgreSQL setup guide for macOS users
07e980b - Add docker-compose.yml for PostgreSQL/pgvector database setup
4142479 - Fix: Fabric category filtering, image display flow, and SupervisorAgent validation
```

---

## 📞 Falls es gar nicht klappt morgen

**Nuclear Option: Bilder ohne show_fabric_images**

Einfachste Lösung wenn Zeit knapp:

1. **In `_execute_rag_tool` direkt Bilder zurückgeben:**
```python
# workflow/nodes.py Zeile 714 nach "Moment, ich zeige dir..."
# Füge direkt fabric_images hinzu:
fabric_images = [
    {
        "url": fabric.get("image_urls", [None])[0] or "https://via.placeholder.com/400x300",
        "fabric_code": fabric.get("fabric_code"),
        "name": fabric.get("name"),
    }
    for fabric in fabrics[:2]
]

# Return message WITH metadata containing fabric_images
return formatted, fabric_images
```

2. **In tools_dispatcher:**
```python
elif next_agent == "rag_tool":
    result, fabric_images = await _execute_rag_tool(...)
    metadata = {}
    if fabric_images:
        metadata["fabric_images"] = fabric_images
    messages.append({
        "role": "assistant",
        "content": result,
        "sender": next_agent,
        "metadata": metadata
    })
```

**Das würde Bilder sofort nach RAG zeigen, ohne extra show_fabric_images Action!**

---

## ⏰ Zeitplan Morgen

**Total: ~60 Minuten**

- 0-30 Min: Quick Fix #1-3 (Workflow-Routing debuggen)
- 30-45 Min: Falls nötig: Nuclear Option (RAG direkt mit Bildern)
- 45-60 Min: Testen + letzte Tweaks

**ZIEL: Funktionierende Bild-Anzeige in 60 Minuten!** 🎯

---

**Good Luck! 🚀**
