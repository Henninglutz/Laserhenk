# CRM Tool Design Issue: api_key Parameter Handling

## Problem

Die `CRMTool.__init__()` Methode kann `api_key=None` nicht explizit setzen:

```python
# tools/crm_tool.py:92
self.api_key = api_key or os.getenv('PIPEDRIVE_API_KEY')
```

**Was passiert:**
```python
CRMTool(api_key=None)  # ← User will MOCK-Mode
# → None or os.getenv(...) → lädt trotzdem ENV Variable! ❌
```

## Warum ist das ein Problem?

1. **Tests können nicht MOCK-Mode erzwingen** wenn ENV Variable gesetzt ist
2. **Explizite `None` wird ignoriert** (unexpected behavior)
3. **Breaking Contract**: Parameter-Wert wird überschrieben

## Lösung: Sentinel Value Pattern

```python
# Better approach
_UNSET = object()  # Sentinel value

class CRMTool:
    def __init__(self, api_key=_UNSET, domain=_UNSET):
        """
        Initialize CRM Tool.

        Args:
            api_key: Pipedrive API key (defaults to env var if not provided)
                    Pass None explicitly to disable API
            domain: Pipedrive domain (defaults to env var if not provided)
        """
        # Distinguish between "not provided" and "explicitly None"
        if api_key is _UNSET:
            self.api_key = os.getenv('PIPEDRIVE_API_KEY')
        else:
            self.api_key = api_key  # Can be None!

        if domain is _UNSET:
            self.domain = os.getenv('PIPEDRIVE_DOMAIN', 'api.pipedrive.com')
        else:
            self.domain = domain

        if self.api_key:
            self.client = PipedriveClient(self.api_key, self.domain)
        else:
            self.client = None
```

## Benefits

✅ `CRMTool()` → lädt ENV Variable (default behavior)
✅ `CRMTool(api_key="xyz")` → verwendet "xyz"
✅ `CRMTool(api_key=None)` → explizit MOCK-Mode (keine API)

## Current Workaround (Test)

```python
# test_crm_integration.py:65
# Temporarily remove API key from environment
original_api_key = os.environ.pop('PIPEDRIVE_API_KEY', None)

try:
    crm_tool = CRMTool()  # Now loads None from env
    # ... test MOCK behavior
finally:
    if original_api_key:
        os.environ['PIPEDRIVE_API_KEY'] = original_api_key
```

## Recommendation

**Option A:** Fix `CRMTool.__init__()` with Sentinel pattern (cleaner)
**Option B:** Keep current workaround in tests (simpler, no breaking changes)

Ich empfehle **Option A** für bessere Code-Qualität.

## Related Files

- `tools/crm_tool.py:84-98` - CRMTool.__init__()
- `test_crm_integration.py:58-94` - Workaround implementation
