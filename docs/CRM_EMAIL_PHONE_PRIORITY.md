# CRM Lead-Erstellung: Email & Telefonnummer Sicherung

## 🎯 Hauptziel: Kontaktdaten sichern

**Priorität #1:** User Email und Telefonnummer müssen im CRM gespeichert werden.

Der Deal ist **optional** - wichtig ist, dass wir den Kontakt nicht verlieren!

---

## ✅ Aktuelle Implementierung

### Person wird IMMER erstellt

```python
# tools/crm_tool.py:123-127
person = self.client.create_person(
    name=lead_data.customer_name,  # ← "Max Mustermann"
    email=lead_data.email,          # ← "max@example.com"
    phone=lead_data.phone,          # ← "+49 123 456789" (optional)
)

# → API Call: POST /v1/persons
# → Body: {
#     "name": "Max Mustermann",
#     "email": ["max@example.com"],
#     "phone": ["+49 123 456789"]
# }
```

**Ergebnis in Pipedrive:**
```
Person ID: 4202
├─ Name: Max Mustermann
├─ Email: max@example.com ✅ GESICHERT
└─ Phone: +49 123 456789 ✅ GESICHERT
```

---

### Deal ist optional

```python
# tools/crm_tool.py:132-140
deal_id = None
if lead_data.deal_value and lead_data.deal_value > 0:
    deal = self.client.create_deal(...)  # ← Nur wenn deal_value gesetzt
    deal_id = str(deal['id'])
```

**Wichtig:**
- ✅ Wenn `deal_value = 0` → Keine Deal, aber Person wird trotzdem erstellt!
- ✅ Wenn `deal_value = None` → Keine Deal, aber Person wird trotzdem erstellt!

---

## 📊 Beispiele

### Beispiel 1: Mit Deal (Standard-Fall)

**Input:**
```python
CRMLeadCreate(
    customer_name="Anna Schmidt",
    email="anna@example.com",
    phone="+49 170 1234567",
    deal_value=2000.0,  # ← Deal wird erstellt
)
```

**Pipedrive:**
```
Person ID: 4202
├─ Email: anna@example.com ✅
└─ Phone: +49 170 1234567 ✅

Deal ID: 5678
├─ Title: "Lead: Anna Schmidt"
├─ Value: 2000 EUR
└─ Person: 4202
```

---

### Beispiel 2: Nur Kontaktdaten (kein Deal)

**Input:**
```python
CRMLeadCreate(
    customer_name="Peter Müller",
    email="peter@example.com",
    phone="+49 160 9876543",
    deal_value=0,  # ← KEIN Deal!
)
```

**Pipedrive:**
```
Person ID: 4203
├─ Email: peter@example.com ✅
└─ Phone: +49 160 9876543 ✅

Deal: NICHT erstellt ❌
```

**Ergebnis:** Kontaktdaten sind trotzdem gesichert! ✅

---

### Beispiel 3: Nur Email (kein Telefon)

**Input:**
```python
CRMLeadCreate(
    customer_name="Julia Werner",
    email="julia@example.com",
    phone=None,  # ← Kein Telefon
    deal_value=1500.0,
)
```

**Pipedrive:**
```
Person ID: 4204
├─ Email: julia@example.com ✅
└─ Phone: (leer)

Deal ID: 5679
├─ Value: 1500 EUR
└─ Person: 4204
```

**Ergebnis:** Email ist gesichert, Phone optional ✅

---

## 🔒 Datensicherung im Workflow

### Wann werden Daten gesammelt?

```
1. HENK1 (Fabric Selection Agent)
   ↓
   Fragt nach Email (für Kontaktsicherung)
   └─> state.customer.email = "max@example.com"
   └─> state.customer.phone = "+49 123 456789" (optional)

2. Design HENK
   ↓
   Mood Board wird generiert & genehmigt

3. TRIGGER: crm_create_lead ✅
   ↓
   Email + Phone werden an Pipedrive gesendet
   └─> Person wird erstellt
   └─> Kontakt ist GESICHERT! ✅
```

---

## ⚠️ Kritischer Check: Email Validation

### Aktueller Stand

**Problem:** Wenn Email `None` ist, schlägt create_person() fehl!

```python
# workflow/nodes_kiss.py:446
customer_email = params.get("customer_email") or state.customer.email

# Was wenn BEIDE None sind?
# → create_person(email=None) → API Error!
```

### Lösung: Validation hinzufügen

```python
# BEFORE calling crm_tool.create_lead():
if not customer_email:
    logger.error("[CRM] Cannot create lead: Email missing!")
    return ToolResult(
        text="⚠️ Email erforderlich für Kontaktsicherung",
        metadata={"error": "missing_email", "success": False}
    )
```

---

## ✅ Best Practice: Email ist Pflicht

### Empfohlene Änderung

**Datei:** `workflow/nodes_kiss.py:437`

```python
async def _crm_create_lead(params: dict, state: HenkGraphState):
    """Create CRM lead in Pipedrive."""
    session_state = _session_state(state)

    # Extract customer data
    customer_name = params.get("customer_name") or session_state.customer.name or "Interessent"
    customer_email = params.get("customer_email") or session_state.customer.email
    customer_phone = params.get("customer_phone") or session_state.customer.phone

    # ✅ CRITICAL: Validate Email BEFORE creating lead
    if not customer_email:
        logger.error(f"[CRM] Lead creation failed: No email provided for {customer_name}")

        # Create MOCK lead to prevent infinite loop
        mock_lead_id = f"NO_EMAIL_{session_state.session_id[:8]}"
        session_state.customer.crm_lead_id = mock_lead_id
        state["session_state"] = session_state

        return ToolResult(
            text="⚠️ Email-Adresse erforderlich für Kontaktsicherung. "
                 "Bitte geben Sie Ihre Email an, damit wir Sie erreichen können.",
            metadata={"error": "missing_email", "crm_lead_id": mock_lead_id}
        )

    # Continue with normal lead creation
    lead_data = CRMLeadCreate(
        customer_name=customer_name,
        email=customer_email,  # ← Garantiert nicht None!
        phone=customer_phone,   # ← Kann None sein (optional)
        notes=f"Mood board: {params.get('mood_image_url', 'N/A')}",
        deal_value=2000.0,
    )

    crm_tool = CRMTool()
    response = await crm_tool.create_lead(lead_data)

    # ... rest of the function
```

---

## 📋 Zusammenfassung

| Item | Status | Priorität |
|------|--------|-----------|
| **Email Speicherung** | ✅ Funktioniert | 🔴 CRITICAL |
| **Phone Speicherung** | ✅ Funktioniert (optional) | 🟡 MEDIUM |
| **Email Validation** | ❌ Fehlt | 🔴 CRITICAL |
| **Deal Erstellung** | ✅ Optional | 🟢 LOW |
| **Duplikat-Prüfung** | ✅ Funktioniert | 🟡 MEDIUM |

---

## 🎯 Finale Antwort: Ja, Email & Phone werden gesichert!

**Was passiert aktuell:**

```
User genehmigt Mood Board
         ↓
Design HENK → action="crm_create_lead"
         ↓
_crm_create_lead() extrahiert:
  • customer.email = "max@example.com"
  • customer.phone = "+49 123 456789"
         ↓
CRMTool.create_lead() ruft Pipedrive API:
  POST /v1/persons
  {
    "name": "Max Mustermann",
    "email": ["max@example.com"],    ✅ GESICHERT
    "phone": ["+49 123 456789"]      ✅ GESICHERT
  }
         ↓
Response: {"data": {"id": 4202, ...}}
         ↓
state.customer.crm_lead_id = "4202"
         ↓
Kontakt ist im CRM! ✅
```

**Deal ist optional** - selbst wenn `deal_value = 0`, wird die Person (mit Email & Phone) trotzdem erstellt!

---

## 🔧 Empfohlener Fix

**Priorität 1:** Email Validation hinzufügen (verhindert Fehler wenn Email fehlt)

Soll ich das implementieren? Es sind nur ~15 Zeilen Code in `workflow/nodes_kiss.py:437`.

---

**Fazit:**
- ✅ Email & Phone werden korrekt im CRM gesichert
- ✅ Deal ist optional (nicht kritisch)
- ⚠️ Email Validation fehlt (sollte hinzugefügt werden)

**Deine Leads sind sicher!** 🎯
