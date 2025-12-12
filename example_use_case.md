# 🎯 Konkretes Anwendungsbeispiel: Maßanzug-Verkauf mit CRM

## Szenario

Ein Kunde besucht deine Website, chattet mit HENK über einen Anzug, und du verfolgst den Lead in Pipedrive.

---

## 📱 Use Case Flow

### 1. Kunde besucht Website (Anonymous)

**Frontend:** Kunde öffnet Chat auf deiner Website

**Backend:** Chat funktioniert ohne Login
```bash
POST /api/chat
{
  "message": "Ich suche einen Anzug für eine Hochzeit"
}
```

**HENK antwortet:** "Wunderbar! Für welche Jahreszeit...?"

### 2. Kunde wird interessiert → Registrierung

**Frontend:** "Erstellen Sie einen Account für personalisierte Empfehlungen"

```bash
POST /api/auth/register
{
  "email": "kunde@example.com",
  "username": "Max Mustermann",
  "password": "SecurePass123!"
}
```

**Response:** JWT Token + User ID

### 3. Personalisierter Chat (Authenticated)

Jetzt mit JWT Token im Header:

```bash
POST /api/chat
Authorization: Bearer eyJ0eXAi...

{
  "message": "Budget ist ca. 2500 Euro, Hochzeit im Juni"
}
```

**HENK:**
- Kennt jetzt die Kunden-Historie
- Kann RAG nutzen für personalisierte Stoff-Empfehlungen
- Session wird dem User zugeordnet

### 4. Lead automatisch in Pipedrive erstellen

**Trigger:** Kunde zeigt ernsthaftes Interesse

```bash
POST /api/crm/lead
Authorization: Bearer eyJ0eXAi...

{
  "name": "Max Mustermann",
  "email": "kunde@example.com",
  "phone": "+49 170 1234567",
  "deal_title": "Hochzeits-Anzug Juni 2025",
  "deal_value": 2500
}
```

**Pipedrive:**
- ✅ Person erstellt
- ✅ Deal erstellt mit 2500 EUR
- ✅ Stage: "Initial Contact"

### 5. Mitarbeiter (Beta-User) sieht Deal-Historie

**Dein Sales-Team** loggt sich als Beta-User ein:

```bash
POST /api/auth/login
{
  "email": "sales@deinfirma.com",
  "password": "TeamPass123!",
  "is_beta_user": true
}
```

**Dann:**

```bash
GET /api/crm/deals?email=kunde@example.com
Authorization: Bearer eyJ0eXAi...
```

**Response:**
```json
{
  "deals": [
    {
      "id": 123,
      "title": "Hochzeits-Anzug Juni 2025",
      "value": 2500,
      "currency": "EUR",
      "status": "open",
      "person_name": "Max Mustermann",
      "created_at": "2025-06-01T10:30:00Z"
    }
  ]
}
```

### 6. Deal Update nach Beratungsgespräch

Nach Termin im Geschäft:

```bash
PUT /api/crm/deal/123
Authorization: Bearer eyJ0eXAi...

{
  "stage_id": 2,
  "value": 2800,
  "status": "won"
}
```

**Pipedrive:** Deal auf "Won" gesetzt, Wert aktualisiert

---

## 🏆 Was wurde erreicht?

1. ✅ **Seamless Customer Journey** - Anonymous → Registered → Lead
2. ✅ **Automatische CRM-Integration** - Kein manuelles Eintragen
3. ✅ **Personalisierung** - User-spezifische Chat-Historie
4. ✅ **Team-Übersicht** - Beta-User sehen alle Deals
5. ✅ **Pipedrive Sync** - Single Source of Truth

---

## 💼 Business Value

### Für den Kunden:
- 💬 Einfacher Chat ohne Registrierung
- 🎯 Personalisierte Empfehlungen
- 📱 Geräte-übergreifende Sessions

### Für dein Team:
- 📊 Automatisches Lead-Tracking
- 🔍 Komplette Kundenhistorie
- 📈 Pipeline-Übersicht in Pipedrive
- ⚡ Keine doppelte Dateneingabe

---

## 🔧 Integration in bestehendes Frontend

### React/Vue Beispiel:

```javascript
// 1. User Registration
const register = async (email, username, password) => {
  const response = await fetch('http://localhost:8000/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, username, password })
  });

  const data = await response.json();

  // Speichere Token
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);

  return data;
};

// 2. Chat senden
const sendMessage = async (message, sessionId = null) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''  // Optional auth
    },
    body: JSON.stringify({ message, session_id: sessionId })
  });

  return await response.json();
};

// 3. Lead erstellen (wenn Kunde interessiert)
const createLead = async (customerData) => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/crm/lead', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(customerData)
  });

  return await response.json();
};

// 4. Deal-Historie abrufen (für Beta-User Dashboard)
const getDeals = async () => {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/crm/deals', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  return await response.json();
};
```

---

## 🎨 UI/UX Flow

### Customer-Facing:

```
┌─────────────────────────────────────┐
│  💬 Chat ohne Login                 │
│  "Hallo! Ich suche einen Anzug..."  │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  📝 Optional: Registrierung         │
│  "Für personalisierte Empfehlungen" │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  🎯 Personalisierter Chat           │
│  + Stoff-Empfehlungen (RAG)         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  📧 "Jemand kontaktiert Sie..."     │
│  → Lead automatisch in Pipedrive    │
└─────────────────────────────────────┘
```

### Admin-Dashboard (Beta-User):

```
┌─────────────────────────────────────┐
│  Dashboard - Sales Team             │
├─────────────────────────────────────┤
│                                     │
│  📊 Aktuelle Deals:                 │
│                                     │
│  • Max M. - Hochzeits-Anzug - 2500€│
│    Status: Open | Juni 2025        │
│                                     │
│  • Anna S. - Business-Anzug - 1800€│
│    Status: Proposal | März 2025    │
│                                     │
│  [Details] [Contact] [Update]      │
└─────────────────────────────────────┘
```

---

## 📈 Metriken & Analytics

Mit diesem Setup kannst du tracken:

1. **Conversion Rate**: Anonymous → Registered
2. **Lead Quality**: Chat-Sessions bis Deal
3. **Response Time**: HENK vs. Human Handoff
4. **Deal Value**: Durchschnittlicher Auftragswert
5. **Win Rate**: Closed/Won vs. Lost

Alle Daten sind in Pipedrive verfügbar + deine eigene Datenbank.

---

## 🚀 Erweiterungsmöglichkeiten

### 1. Appointment Scheduling
```bash
POST /api/appointments
{
  "customer_id": "...",
  "date": "2025-06-15",
  "type": "measurement"
}
```

### 2. Fabric Recommendations
```bash
GET /api/fabrics/search?style=formal&season=summer
```

### 3. Order Tracking
```bash
GET /api/orders/customer/{customer_id}
```

### 4. Email Notifications
- Lead erstellt → Team-Benachrichtigung
- Deal gewonnen → Automatische Bestätigungs-Email

---

**Das ist die Power deines neuen Flask-Systems! 💪**
