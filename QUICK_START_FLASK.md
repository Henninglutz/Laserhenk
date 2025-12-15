# 🚀 Quick Start Guide - Flask App

## 📍 Wo liegt was?

```
Laserhenk/
├── .env                    # ← SECRETS HIER! (neu erstellt)
├── .flaskenv              # ← Flask Config
├── run_flask.py           # ← Flask starten hiermit!
├── demo_flask_usage.py    # ← Demo-Script zum Testen
│
├── app/                   # ← FLASK APP hier!
│   ├── __init__.py       # Flask Factory
│   ├── auth.py           # Login/Register
│   ├── api.py            # Chat & Sessions
│   ├── crm.py            # Pipedrive
│   └── middleware.py     # JWT Auth
│
└── server_old.py         # Alte Version (Backup)
```

> **Hinweis zu Entry Points:**
> Für die produktive/aktuelle API wird der Flask-Server über `run_flask.py` gestartet. Die in den Tests referenzierten Funktionen `create_http_server`, `process_chat` und `run` kommen aus `server.py`, das lediglich als dünne Weiterleitung nach `server_old.py` dient. Beide Entry Points landen also beim selben Flask-Stack und denselben `/api/*`-Endpoints.

## 🔑 Secrets einrichten (`.env` Datei)

Die `.env` Datei wurde bereits erstellt! Du musst nur die Secrets eintragen:

### 1. Flask Secrets (WICHTIG!)

```bash
# Generiere sichere Keys:
python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

Trage die generierten Keys in `.env` ein:

```bash
# Flask Configuration
FLASK_SECRET_KEY=<dein-generierter-key>
JWT_SECRET_KEY=<dein-generierter-jwt-key>
PORT=8000
```

### 2. Pipedrive API Key (für CRM)

Gehe zu: https://app.pipedrive.com/settings/api

```bash
# In .env eintragen:
PIPEDRIVE_API_KEY=dein-pipedrive-key-hier
```

### 3. OpenAI Key (bereits vorhanden?)

```bash
OPENAI_API_KEY=sk-dein-openai-key
```

### 4. Database (bereits konfiguriert)

```bash
DATABASE_URL=postgresql://henk_user:VerySecurePassword123!@localhost:5432/henk_rag
```

## ⚡ Flask App starten

### Schritt 1: Dependencies installieren

```bash
pip install -r requirements.txt
```

**Wichtige neue Packages:**
- `flask>=3.0.0`
- `flask-cors>=4.0.0`
- `flask-jwt-extended>=4.6.0`
- `argon2-cffi>=23.1.0`

### Schritt 2: Flask starten

```bash
python run_flask.py
```

**Oder mit Flask CLI:**

```bash
flask run --host=0.0.0.0 --port=8000
```

### Schritt 3: Testen

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Erwartete Antwort:**
```json
{"status": "ok", "service": "laserhenk-flask"}
```

## 🎯 Was kannst du jetzt machen?

### Beispiel 1: Beta-User registrieren

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "max@example.com",
    "username": "max",
    "password": "SecurePass123!",
    "is_beta_user": true
  }'
```

**Response:**
```json
{
  "message": "User erfolgreich registriert",
  "user": {
    "user_id": "abc-123",
    "email": "max@example.com",
    "username": "max",
    "is_beta_user": true
  },
  "access_token": "eyJ0eXAiOiJKV1...",
  "refresh_token": "eyJ0eXAiOiJKV1...",
  "token_type": "Bearer"
}
```

### Beispiel 2: Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "max@example.com",
    "password": "SecurePass123!"
  }'
```

### Beispiel 3: Chat (mit Token)

```bash
# Speichere Token aus Login:
TOKEN="eyJ0eXAiOiJKV1..."

# Chat mit AI:
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "Ich suche einen Business-Anzug"
  }'
```

### Beispiel 4: Lead in Pipedrive erstellen

```bash
curl -X POST http://localhost:8000/api/crm/lead \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Max Mustermann",
    "email": "max@example.com",
    "phone": "+49 170 1234567",
    "deal_title": "Business-Anzug",
    "deal_value": 2000
  }'
```

### Beispiel 5: Deal-Historie abrufen (Beta-User only)

```bash
curl -X GET http://localhost:8000/api/crm/deals \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "deals": [
    {
      "id": 123,
      "title": "Business-Anzug",
      "value": 2000,
      "currency": "EUR",
      "status": "open",
      "person_name": "Max Mustermann"
    }
  ],
  "count": 1
}
```

## 🎬 Demo-Script nutzen

Ein komplettes Demo-Script ist auch verfügbar:

```bash
python demo_flask_usage.py
```

**Das Script zeigt:**
1. ✅ Beta-User Registration & Login
2. ✅ Chat mit dem AI Agent
3. ✅ Lead in Pipedrive erstellen
4. ✅ Deal-Historie abrufen
5. ✅ Anonymen Chat ohne Login

## 🔐 Beta-User vs. Normal-User

### Normal-User kann:
- ✅ Registrieren & Login
- ✅ Chat mit AI
- ✅ Lead erstellen
- ✅ Sessions verwalten

### Beta-User kann zusätzlich:
- ✅ **Deal-Historie** in Pipedrive abrufen
- ✅ **Deal-Details** anzeigen
- ✅ Zukünftige Premium-Features

### Beta-User erstellen:

```json
{
  "is_beta_user": true  // ← Dieses Flag setzen!
}
```

## 🔧 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'flask'"

```bash
pip install -r requirements.txt
```

### Problem: "JWT_SECRET_KEY not set"

Prüfe deine `.env` Datei:
```bash
cat .env | grep JWT_SECRET_KEY
```

### Problem: "Pipedrive API error"

1. Prüfe API Key: https://app.pipedrive.com/settings/api
2. Setze in `.env`:
   ```bash
   PIPEDRIVE_API_KEY=dein-key-hier
   ```

### Problem: Port 8000 belegt

Ändere Port in `.env`:
```bash
PORT=8080  # oder ein anderer freier Port
```

## 📊 Alle Endpoints

### 🔓 Ohne Authentication:
- `GET /health` - Server Status
- `POST /api/auth/register` - Registrierung
- `POST /api/auth/login` - Login
- `POST /api/auth/refresh` - Token Refresh

### 🔐 Mit Authentication:
- `GET /api/auth/me` - User Info
- `POST /api/auth/change-password` - Passwort ändern
- `POST /api/session` - Session erstellen
- `POST /api/chat` - Chat (funktioniert auch ohne Auth)
- `GET /api/sessions` - Sessions auflisten
- `POST /api/crm/lead` - Lead erstellen

### 👑 Beta-User Only:
- `GET /api/crm/deals` - Deal-Historie
- `GET /api/crm/deal/<id>` - Deal Details

## 💡 Nächste Schritte

1. **Secrets setzen** in `.env`
2. **Dependencies installieren**: `pip install -r requirements.txt`
3. **Flask starten**: `python run_flask.py`
4. **Demo testen**: `python demo_flask_usage.py`
5. **Frontend anpassen** auf neue Endpoints

## 📚 Weitere Dokumentation

- `FLASK_MIGRATION_SUMMARY.md` - Komplette Migration Details
- `README.md` - Projekt Übersicht
- `TODO.md` - Roadmap

---

**Viel Erfolg! 🚀**
