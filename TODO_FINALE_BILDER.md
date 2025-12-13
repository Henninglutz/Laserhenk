# FINALE TODO - Echte Stoffbilder anzeigen

## ✅ ERFOLGE HEUTE:
1. ✅ Nuclear Option: RAG gibt fabric_images zurück
2. ✅ Color Extraction funktioniert (blau → blue/navy)
3. ✅ Echte Stoffbilder gefunden in `storage/fabrics/images/`
4. ✅ API sendet fabric_images korrekt

## 🔴 LETZTE SCHRITTE (30 Min):

### 1. Flask: Serve local fabric images (10 Min)

**In `app.py` oder `run_flask.py` hinzufügen:**

```python
from flask import send_from_directory
import os

# Add route for fabric images
@app.route('/fabrics/images/<path:filename>')
def serve_fabric_image(filename):
    """Serve fabric images from storage directory."""
    images_dir = os.path.join(app.root_path, 'storage', 'fabrics', 'images')
    return send_from_directory(images_dir, filename)
```

**Test:** http://localhost:3000/fabrics/images/10C4017.jpg sollte Bild zeigen!

### 2. RAG Tool: Use local images (10 Min)

**In `workflow/nodes.py` Zeile ~720:**

```python
# Get image URL - PREFER LOCAL FILES!
image_url = None
fabric_code_clean = fabric.fabric_code.replace('/', '_')  # Clean filename
local_image_path = f"/fabrics/images/{fabric_code_clean}.jpg"

# Check if local image exists (assume it does for now)
image_url = local_image_path  # Use local path

# Fallback if needed
if not image_url:
    image_url = f"https://via.placeholder.com/400x300?text={fabric.fabric_code}"
```

### 3. Frontend: Ensure images render (5 Min)

**Check `static/app.js` has image rendering:**

```javascript
if (data.fabric_images && data.fabric_images.length > 0) {
    data.fabric_images.forEach(img => {
        const imgElement = document.createElement('img');
        imgElement.src = img.url;  // Should load /fabrics/images/XXX.jpg
        imgElement.alt = img.fabric_code;
        // Append to chat...
    });
}
```

### 4. Database: Update image_url paths (Optional, 15 Min)

**Falls Zeit:**

```sql
-- Update fabrics table to include local image paths
UPDATE fabrics
SET additional_metadata = jsonb_set(
    COALESCE(additional_metadata, '{}'::jsonb),
    '{image_url}',
    to_jsonb('/fabrics/images/' || fabric_code || '.jpg')
)
WHERE EXISTS (
    SELECT 1 FROM ... -- Check if image file exists
);
```

---

## 🎯 ZIEL:

**User schreibt:** "zeig mir blaue stoffe"

**System zeigt:**
- ✅ Text mit Stoffdetails
- ✅ 2 ECHTE Bilder von Stoffen (z.B. `/fabrics/images/ME4-599.101_334.jpg`)
- ✅ Korrekte blaue Farben
- ✅ Keine Platzhalter mehr!

---

## 🚨 BEKANNTE ISSUES:

1. **SupervisorAgent gibt String zurück** - JSON parsing funktioniert aber (Fallback active)
2. **.env Zeile 108** - Nur Warnung, nicht kritisch
3. **Farb-Context geht verloren** - Bei 2. Nachfrage vergisst System Farbe
4. **Frontend rendering** - Images könnten nicht gerendert werden (JS check needed)

---

## ⏰ ZEITPLAN MORGEN:

**Total: 30 Minuten**

1. **0-10 Min:** Flask route für /fabrics/images/
2. **10-20 Min:** RAG tool nutzt lokale Bild-Pfade
3. **20-25 Min:** Test im Browser
4. **25-30 Min:** Falls Fehler: Debug + Fix

**Nach 30 Min: FERTIG oder ABBRUCH!**

---

## 🔥 NUCLEAR FALLBACK (falls alles schief geht):

**DALL-E Outfits mit Platzhaltern:**

Wenn Stoffbilder nicht klappen:
- Nutze Platzhalter-URLs
- DALL-E generiert Outfit basierend auf Text-Beschreibung
- Später echte Bilder nachrüsten

---

**Stand:** 13. Dez 2025, 21:10 Uhr
**Status:** 80% FERTIG! Nur noch Bild-Serving fehlt!
**Nächster Schritt:** Flask route + lokale Pfade

Good luck! 🚀
