# CRM Lead & Deal Erstellung - Workflow Dokumentation

## 📘 Pipedrive Konzepte

### Was ist der Unterschied zwischen "Lead", "Person" und "Deal"?

In **Pipedrive** gibt es diese Entitäten:

```
┌─────────────────────────────────────────────────────────┐
│  PERSON (Kontakt)                                       │
│  ─────────────────                                      │
│  - Name: "Max Mustermann"                               │
│  - Email: max@example.com                               │
│  - Phone: +49 123 456789                                │
│  - Person ID: 4202                                      │
│                                                          │
│  ┌──────────────────────────────────────────┐          │
│  │  DEAL (Geschäftschance)                  │          │
│  │  ───────────────────────                 │          │
│  │  - Title: "Hochzeitsanzug"               │          │
│  │  - Value: 2000 EUR                       │          │
│  │  - Stage: "Erstgespräch"                 │          │
│  │  - Deal ID: 5678                         │          │
│  │  - Linked to Person: 4202                │          │
│  └──────────────────────────────────────────┘          │
│                                                          │
│  ┌──────────────────────────────────────────┐          │
│  │  DEAL (weiteres Geschäft)                │          │
│  │  - Title: "Business-Anzug"               │          │
│  │  - Value: 1500 EUR                       │          │
│  │  - Deal ID: 5679                         │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

**Wichtig:**
- Eine **Person** = Ein Kontakt (Customer)
- Ein **Deal** = Eine Verkaufschance/Opportunity
- Eine Person kann **mehrere Deals** haben
- Ein Deal ist **immer** mit einer Person verknüpft

**"Lead" in unserem Code** = Person + optional Deal

---

## 🔄 Workflow: Wann wird was erstellt?

### Phase 1: Mood Board Approval → Person + Deal erstellen

**Trigger:** User genehmigt Mood Board in Design HENK

**Datei:** `agents/design_henk.py:266`

```python
# NACH Mood Board Approval
if state.image_state.mood_board_approved and state.customer.email:
    return AgentDecision(
        action="crm_create_lead",  # ← Erstellt Person + Deal
        action_params={
            "customer_name": "Max Mustermann",
            "customer_email": "max@example.com",
            "customer_phone": "+49 123 456789",
            "mood_image_url": "https://...",
        }
    )
```

**Was passiert:**
1. ✅ Prüfe ob Email bereits in Pipedrive existiert
2. ✅ Falls **NEIN**: Erstelle neue Person
3. ✅ Falls **JA**: Verwende existierende Person (Duplikatsprüfung!)
4. ✅ Erstelle Deal (wenn `deal_value > 0`)

---

### Phase 2: CRM Lead Creation

**Datei:** `workflow/nodes_kiss.py:437`

```python
async def _crm_create_lead(params: dict, state: HenkGraphState):
    """Create CRM lead in Pipedrive."""

    # 1. Kundendaten aus Session State extrahieren
    customer_name = state.customer.name or "Interessent"
    customer_email = state.customer.email
    customer_phone = state.customer.phone

    # 2. Lead-Daten vorbereiten
    lead_data = CRMLeadCreate(
        customer_name=customer_name,
        email=customer_email,
        phone=customer_phone,
        notes=f"Mood board: {mood_image_url}",
        deal_value=2000.0,  # ← Default: 2000 EUR
    )

    # 3. CRM Tool aufrufen
    crm_tool = CRMTool()
    response = await crm_tool.create_lead(lead_data)

    # 4. Lead ID im Session State speichern
    state.customer.crm_lead_id = response.lead_id  # ← z.B. "4202"
```

---

### Phase 3: Was macht `CRMTool.create_lead()`?

**Datei:** `tools/crm_tool.py:100`

```python
async def create_lead(self, lead_data: CRMLeadCreate) -> CRMLeadResponse:
    """Create lead in Pipedrive."""

    # SCHRITT 1: Duplikatsprüfung
    person = self.client.get_person_by_email(lead_data.email)

    if not person:
        # SCHRITT 2a: Person ERSTELLEN (neu)
        person = self.client.create_person(
            name=lead_data.customer_name,
            email=lead_data.email,
            phone=lead_data.phone,
        )
        # → API Call: POST /v1/persons
        # → Response: {"data": {"id": 4202, "name": "Max", ...}}

    # SCHRITT 2b: Existierende Person verwenden (Duplikat)
    person_id = person['id']  # z.B. 4202

    # SCHRITT 3: Deal erstellen (NUR wenn deal_value > 0)
    deal_id = None
    if lead_data.deal_value and lead_data.deal_value > 0:
        deal = self.client.create_deal(
            title=f"Lead: {lead_data.customer_name}",
            person_id=person_id,  # ← Verknüpfung!
            value=lead_data.deal_value,  # z.B. 2000.0
            currency='EUR',
        )
        # → API Call: POST /v1/deals
        # → Response: {"data": {"id": 5678, "title": "Lead: Max", ...}}
        deal_id = str(deal['id'])

    # SCHRITT 4: Response zurückgeben
    return CRMLeadResponse(
        lead_id=str(person_id),    # ← "4202" (Person ID)
        deal_id=deal_id,           # ← "5678" (Deal ID) oder None
        success=True,
        message=f'Lead erfolgreich erstellt (Person ID: {person_id})',
    )
```

---

## 📊 Wann wird ein Deal erstellt?

### Bedingung im Code:

```python
# tools/crm_tool.py:133
if lead_data.deal_value and lead_data.deal_value > 0:
    deal = self.client.create_deal(...)
```

**Deal wird erstellt wenn:**
- ✅ `deal_value` ist gesetzt UND
- ✅ `deal_value > 0`

**Deal wird NICHT erstellt wenn:**
- ❌ `deal_value` ist `None`
- ❌ `deal_value == 0`

---

## 🔧 Wie wird `deal_value` gesetzt?

### 1. **Automatisch im Workflow** (`workflow/nodes_kiss.py:455`)

```python
lead_data = CRMLeadCreate(
    customer_name=customer_name,
    email=customer_email,
    phone=customer_phone,
    notes=f"Mood board: {params.get('mood_image_url', 'N/A')}",
    deal_value=2000.0,  # ← HARD-CODED: Immer 2000 EUR!
)
```

**Problem:** Der Wert ist aktuell **fest kodiert** auf 2000 EUR.

**Empfehlung:** Budget aus Session State verwenden:
```python
deal_value=state.customer.budget or 2000.0
```

### 2. **Manuell via Flask API** (`app/crm.py:230`)

```python
POST /api/crm/lead
{
  "name": "Max Mustermann",
  "email": "max@example.com",
  "deal_title": "Hochzeitsanzug",  # ← Optional
  "deal_value": 2000.0              # ← Optional
}
```

**Flask Endpoint-Logik:**
```python
if data.get('deal_title'):
    deal = client.create_deal(
        title=data['deal_title'],
        person_id=person_id,
        value=data.get('deal_value', 0),  # ← Default 0 wenn fehlt
    )
```

---

## 📋 Zusammenfassung: Der komplette Flow

```
┌──────────────────────────────────────────────────────────────┐
│  USER JOURNEY                                                │
└──────────────────────────────────────────────────────────────┘

1. User chattet mit HENK1 (Fabric Selection)
   └─> Email wird gesammelt

2. Handoff zu Design HENK
   └─> Mood Board wird generiert

3. User genehmigt Mood Board ✅
   └─> Trigger: crm_create_lead

4. _crm_create_lead() wird aufgerufen
   │
   ├─> Check: Email bereits in Pipedrive?
   │   ├─> JA: Verwende existierende Person ID
   │   └─> NEIN: Erstelle neue Person
   │
   └─> Check: deal_value > 0?
       ├─> JA: Erstelle Deal (2000 EUR)
       └─> NEIN: Kein Deal

5. Response:
   └─> lead_id: "4202" (Person ID)
   └─> deal_id: "5678" (Deal ID) oder None

6. lead_id wird in Session State gespeichert:
   └─> state.customer.crm_lead_id = "4202"

7. Handoff zu LASERHENK (Terminvereinbarung)
   └─> LASERHENK kann lead_id verwenden für Notizen/Updates
```

---

## 🎯 Beispiele

### Beispiel 1: Neuer Kunde, mit Deal

**Input:**
```python
CRMLeadCreate(
    customer_name="Anna Schmidt",
    email="anna@example.com",
    phone="+49 170 1234567",
    deal_value=2000.0,
)
```

**Pipedrive Actions:**
```
1. GET /v1/persons/search?term=anna@example.com
   └─> Response: {"data": {"items": []}}  ← Nicht gefunden

2. POST /v1/persons
   Body: {"name": "Anna Schmidt", "email": ["anna@example.com"], ...}
   └─> Response: {"data": {"id": 4202, ...}}

3. POST /v1/deals
   Body: {"title": "Lead: Anna Schmidt", "person_id": 4202, "value": 2000.0}
   └─> Response: {"data": {"id": 5678, ...}}
```

**Output:**
```python
CRMLeadResponse(
    lead_id="4202",      # Person ID
    deal_id="5678",      # Deal ID
    success=True,
    message="Lead erfolgreich erstellt (Person ID: 4202)"
)
```

---

### Beispiel 2: Existierender Kunde (Duplikat)

**Input:**
```python
CRMLeadCreate(
    customer_name="Anna Schmidt",
    email="anna@example.com",  # ← GLEICHE Email!
    phone="+49 170 1234567",
    deal_value=1500.0,
)
```

**Pipedrive Actions:**
```
1. GET /v1/persons/search?term=anna@example.com
   └─> Response: {"data": {"items": [{"item": {"id": 4202, ...}}]}}
   └─> ✅ GEFUNDEN! Verwende existierende Person

2. POST /v1/deals (NEUER Deal für existierende Person!)
   Body: {"title": "Lead: Anna Schmidt", "person_id": 4202, "value": 1500.0}
   └─> Response: {"data": {"id": 5679, ...}}
```

**Output:**
```python
CRMLeadResponse(
    lead_id="4202",      # ← Gleiche Person ID!
    deal_id="5679",      # ← NEUER Deal ID!
    success=True,
    message="Lead erfolgreich erstellt (Person ID: 4202)"
)
```

**Ergebnis in Pipedrive:**
```
Person "Anna Schmidt" (ID: 4202)
  ├─ Deal #1: "Lead: Anna Schmidt" - 2000 EUR (ID: 5678)
  └─ Deal #2: "Lead: Anna Schmidt" - 1500 EUR (ID: 5679)
```

---

### Beispiel 3: Nur Person, kein Deal

**Input:**
```python
CRMLeadCreate(
    customer_name="Peter Müller",
    email="peter@example.com",
    deal_value=0,  # ← KEIN Deal!
)
```

**Pipedrive Actions:**
```
1. GET /v1/persons/search?term=peter@example.com
   └─> Response: {"data": {"items": []}}

2. POST /v1/persons
   Body: {"name": "Peter Müller", "email": ["peter@example.com"]}
   └─> Response: {"data": {"id": 4203, ...}}

3. Deal wird NICHT erstellt (deal_value == 0)
```

**Output:**
```python
CRMLeadResponse(
    lead_id="4203",
    deal_id=None,  # ← Kein Deal!
    success=True,
    message="Lead erfolgreich erstellt (Person ID: 4203)"
)
```

---

## 🔍 Kritische Fragen & Antworten

### Q1: Was passiert wenn Email fehlt?

**A:** Aktuell wird trotzdem versucht ein Lead zu erstellen:
```python
# workflow/nodes_kiss.py:446
customer_email = params.get("customer_email") or state.customer.email
# Falls beide None → email = None
```

**Problem:** `create_person(email=None)` wird fehlschlagen.

**Lösung:** Validation hinzufügen (siehe `CRM_REVIEW.md` Issue #2)

### Q2: Kann ein Deal ohne Person existieren?

**A:** Nein! In Pipedrive ist ein Deal **immer** mit einer Person verknüpft.

### Q3: Wann wird `deal_value` aktualisiert?

**A:** Aktuell **NIE automatisch**. Deals werden bei Lead-Erstellung erstellt, aber nicht später aktualisiert.

**Feature Request:** Deal-Update nach Fabric-Auswahl?
```python
# Wenn User teureren Stoff wählt:
await crm_tool.update_deal(deal_id, value=3500.0)
```

### Q4: Was ist `crm_lead_id` im Session State?

**A:** Das ist die **Person ID** aus Pipedrive:
```python
# models/customer.py:33
crm_lead_id: Optional[str] = Field(None, description="PIPEDRIVE CRM Lead ID")

# Nach Lead-Erstellung:
state.customer.crm_lead_id = "4202"  # ← Person ID, NICHT Deal ID!
```

---

## 🚨 Wichtige Hinweise

### 1. **Hard-coded Deal Value**

```python
# workflow/nodes_kiss.py:455
deal_value=2000.0,  # ← IMMER 2000 EUR!
```

**Problem:** Ignoriert User-Budget.

**Fix:**
```python
deal_value=state.customer.get('budget') or 2000.0
```

### 2. **Duplikat-Logik**

**Gut:** Email-basierte Duplikatserkennung funktioniert!
```python
# tools/crm_tool.py:119
person = self.client.get_person_by_email(lead_data.email)
if not person:
    person = self.client.create_person(...)  # Nur wenn nicht vorhanden
```

**Ergebnis:** Gleicher Kunde = 1 Person, mehrere Deals ✅

### 3. **MOCK-Lead Fallback**

Wenn Pipedrive nicht konfiguriert:
```python
# workflow/nodes_kiss.py:476
mock_lead_id = f"MOCK_CRM_{session_id[:8]}"
state.customer.crm_lead_id = mock_lead_id
```

**Verhindert:** Infinite Loop bei fehlender API-Konfiguration ✅

---

## 📝 Empfehlungen

### Priority 1: Deal Value dynamisch

```python
# Aus Session State Budget holen
budget = state.customer.get('budget') or 2000.0

lead_data = CRMLeadCreate(
    customer_name=customer_name,
    email=customer_email,
    deal_value=budget,  # ← Dynamisch!
)
```

### Priority 2: Email Validation

```python
if not customer_email:
    raise ValueError("Email erforderlich für CRM Lead-Erstellung")
```

### Priority 3: Deal Title personalisieren

```python
# Statt:
title=f"Lead: {customer_name}"

# Besser:
title=f"{event_type or 'Anzug'} - {customer_name}"
# z.B. "Hochzeitsanzug - Max Mustermann"
```

---

## 📚 Relevante Dateien

| Datei | Beschreibung |
|-------|--------------|
| `agents/design_henk.py:266` | Trigger für CRM Lead-Erstellung |
| `workflow/nodes_kiss.py:437` | `_crm_create_lead()` Tool Function |
| `tools/crm_tool.py:100` | `CRMTool.create_lead()` Implementation |
| `app/crm.py:188` | Flask REST API Endpoint |
| `models/customer.py:33` | `crm_lead_id` Field Definition |

---

**Autor:** Claude
**Datum:** 2025-12-19
**Version:** 1.0
