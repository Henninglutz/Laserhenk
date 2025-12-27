# Umstellung der Image-Generation (Vertex Imagen 3 + DALL·E Fallback)

Diese Notiz fasst die Architekturänderungen zusammen, die den Wechsel zu Google Vertex AI Imagen 3 als primären Provider, die Prompt-Auslagerung und die policy-konforme Bildgenerierung betreffen.

## Architekturüberblick
- **PromptLoader** (`backend/prompts/loader.py`): Lädt Jinja2-Templates aus `backend/prompts/image/` und rendert sie mit Variablen zur Laufzeit. Templates enthalten keine Hardcoded-Prompts mehr im Code und können gemeinsam genutzte Regeln (`base_rules.md`) einbinden.
- **Provider-Abstraktion** (`backend/services/image_providers/base.py`): Ein gemeinsames Protokoll stellt sicher, dass alle Provider `generate()` asynchron implementieren und immer Bildbytes (keine URLs) zurückliefern.
- **ImagenProvider** (`backend/services/image_providers/imagen_provider.py`): Standardprovider, der das Vertex AI REST-Endpoint aufruft, Base64-kodierte Bildbytes dekodiert und robuste Fehlerbehandlung/Logging liefert.
- **DalleProvider** (`backend/services/image_providers/dalle_provider.py`): Fallback-Provider, nutzt OpenAI `images.generate`, vereinheitlicht die Ausgabe zu Bytes (Download bei URL, sonst Base64-Decode).
- **ImageService** (`backend/services/image_service.py`): Orchestriert Prompt-Rendering, Provider-Aufruf, Policy-Check (`ImagePolicyDecision.allowed_source`), und übernimmt das bestehende PIL-Compositing (Moodboard mit Fabric-Thumbnails, Product-Sheet-Overlay). Der Legacy-Wrapper `get_dalle_tool()` delegiert intern, sodass Aufrufer unverändert bleiben.

## Environment-Variablen
Die Providerwahl und Endpunkte sind rein per ENV steuerbar. Relevante Variablen:

| Variable | Zweck |
| --- | --- |
| `IMAGE_PROVIDER` | Aktiver Provider: `imagen` (Default) oder `dalle`. Nicht passende Policy-Quellen werden blockiert. |
| `GCP_PROJECT` | Projekt-ID für Vertex AI (Imagen). |
| `GCP_LOCATION` | Region, Standard `europe-west4`. |
| `IMAGEN_MODEL` | Modellname, Standard `imagen-3.0-generate-002`. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Pfad zur Service-Account-JSON für Vertex AI. |
| `OPENAI_API_KEY` | API-Key für DALL·E Fallback. |

Weitere interne Parameter wie Größe/Qualität werden an den jeweiligen Provider durchgereicht, bleiben für Aufrufer unverändert und orientieren sich an den bisherigen DALLEImageRequest-Feldern.

## Beispiel `.env`
```
IMAGE_PROVIDER=imagen
GCP_PROJECT=your-project-id
GCP_LOCATION=europe-west4
IMAGEN_MODEL=imagen-3.0-generate-002
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
OPENAI_API_KEY=your-openai-key
```

## Laufzeitverhalten
1. Aufrufer verwenden weiterhin die bisherigen Service-Einstiege; `get_image_service()` sorgt für die einmalige Initialisierung von Provider + PromptLoader.
2. Vor jedem Request wird die Policy geprüft: Wenn `allowed_source` nicht dem aktiven Provider entspricht, wird der Request blockiert und als `policy_blocked` markiert.
3. Erfolgreiche Antworten werden als Bytes geöffnet (`PIL.Image.open(BytesIO(...))`), Compositing läuft wie zuvor, Ergebnisse landen unter `/static/generated_images/`.
