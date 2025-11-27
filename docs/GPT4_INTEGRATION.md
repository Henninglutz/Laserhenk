# GPT-4 Integration Guide

## Overview

The HENK agent system now supports GPT-4 powered intelligent decision-making for enhanced conversational AI capabilities.

## Features

### 🤖 LLM-Enhanced Agents

All agents can optionally use GPT-4 for:
- **Intelligent routing decisions**
- **Natural language conversations**
- **Context-aware responses**
- **Adaptive customer interaction**

### 🔄 Graceful Fallback

- Agents work with OR without LLM
- State-based logic as fallback
- No breaking changes to existing code
- Optional activation per agent

## Setup

### 1. Install Dependencies

```bash
pip install openai>=1.10.0 pydantic-settings>=2.1.0
```

### 2. Configure API Key

Add to `.env`:
```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview
```

### 3. Verify Installation

```bash
python examples/test_llm_integration.py
```

## Architecture

### LLM Service (`services/llm_service.py`)

Central service for all LLM operations:

```python
from services.llm_service import LLMService

llm = LLMService()

# Generate conversational response
response = await llm.generate_response(
    system_prompt="You are HENK1...",
    user_message="Customer needs a suit for a wedding",
    context={"customer_type": "new"},
)

# Generate structured response
from pydantic import BaseModel

class Decision(BaseModel):
    next_agent: str
    action: str

decision = await llm.generate_structured_response(
    system_prompt="...",
    user_message="...",
    response_model=Decision,
)
```

### System Prompts

Pre-configured prompts for each agent:

- **OPERATOR_SYSTEM_PROMPT**: Routing logic
- **HENK1_SYSTEM_PROMPT**: Needs assessment (AIDA)
- **DESIGN_HENK_SYSTEM_PROMPT**: Design preferences
- **LASERHENK_SYSTEM_PROMPT**: Measurements

### LLM Mixin (`agents/llm_mixin.py`)

Optional mixin for agent classes:

```python
from agents.llm_mixin import LLMMixin
from agents.base import BaseAgent

class MyAgent(LLMMixin, BaseAgent):
    def __init__(self, enable_llm=True):
        super().__init__(
            agent_name="my_agent",
            enable_llm=enable_llm
        )

    async def process(self, state):
        # Use LLM if enabled
        if self.enable_llm:
            response = await self.generate_conversational_response(
                system_prompt=MY_SYSTEM_PROMPT,
                user_message="...",
                context={"state": state.model_dump()},
            )
        else:
            # Fallback to state-based logic
            response = self._state_based_logic(state)

        return response
```

## Agent-Specific Integration

### HENK1 (Needs Assessment)

**Purpose**: AIDA principle, customer onboarding

**System Prompt Highlights**:
- Warm, professional greeting
- Open-ended questions
- Build rapport and trust
- Guide to next phase

**Example**:
```python
from services.llm_service import LLMService, HENK1_SYSTEM_PROMPT

llm = LLMService()
response = await llm.generate_response(
    system_prompt=HENK1_SYSTEM_PROMPT,
    user_message="New customer needs a suit for a wedding",
)
```

### Design HENK (Design Preferences)

**Purpose**: Collect design preferences, generate mood images

**System Prompt Highlights**:
- Query RAG for options
- Explain design choices
- Educational and consultative
- Use customer history

**Example**:
```python
from services.llm_service import LLMService, DESIGN_HENK_SYSTEM_PROMPT

response = await llm.generate_response(
    system_prompt=DESIGN_HENK_SYSTEM_PROMPT,
    user_message="Ask about lapel style preferences",
    context={"customer_history": rag_data},
)
```

### LASERHENK (Measurements)

**Purpose**: Measurement collection (SAIA 3D or manual)

**System Prompt Highlights**:
- Explain measurement options
- Offer SAIA 3D benefits
- Schedule appointments
- Professional and reassuring

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (defaults shown)
OPENAI_MODEL=gpt-4-turbo-preview

# Google Service Account (for RAG)
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
GOOGLE_DRIVE_FOLDER_ID=...
```

### Settings Class

```python
from config.settings import get_settings

settings = get_settings()
print(settings.openai_api_key)  # From .env
print(settings.openai_model)    # gpt-4-turbo-preview
```

## Testing

### Unit Tests

```bash
# Test LLM service
python examples/test_llm_integration.py

# Test with specific agent
python -c "
import asyncio
from services.llm_service import LLMService, HENK1_SYSTEM_PROMPT

async def test():
    llm = LLMService()
    response = await llm.generate_response(
        system_prompt=HENK1_SYSTEM_PROMPT,
        user_message='Test greeting',
    )
    print(response)

asyncio.run(test())
"
```

### Integration Tests

```bash
# Run full workflow with LLM
python main.py --enable-llm

# Run without LLM (state-based only)
python main.py
```

## Cost Optimization

### Model Selection

- **gpt-4-turbo-preview**: Best quality, higher cost
- **gpt-4**: Stable, production-ready
- **gpt-3.5-turbo**: Lower cost, good for simple tasks

### Token Management

```python
# Limit tokens for cost control
response = await llm.generate_response(
    system_prompt=prompt,
    user_message=message,
    max_tokens=200,      # Limit response length
    temperature=0.7,     # Lower = more focused
)
```

### Caching

```python
# Cache common queries
from functools import lru_cache

@lru_cache(maxsize=100)
def get_system_prompt(agent_name: str) -> str:
    return {...}[agent_name]
```

## Error Handling

### Graceful Degradation

```python
try:
    llm = LLMService()
    response = await llm.generate_response(...)
except Exception as e:
    # Fall back to state-based logic
    logger.warning(f"LLM unavailable: {e}")
    response = fallback_logic(state)
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def llm_with_retry(...):
    return await llm.generate_response(...)
```

## Best Practices

### 1. System Prompt Design

✅ **Do**:
- Be specific about agent role
- Include output format requirements
- Provide example interactions
- Set tone and style guidelines

❌ **Don't**:
- Make prompts too long (> 1000 tokens)
- Include sensitive information
- Use vague instructions

### 2. Context Management

✅ **Do**:
- Pass relevant state only
- Format context clearly
- Include customer history when available

❌ **Don't**:
- Send entire database
- Include unnecessary details
- Expose API keys in context

### 3. Temperature Settings

- **0.0-0.3**: Deterministic, routing decisions
- **0.4-0.7**: Balanced, general conversation
- **0.8-1.0**: Creative, mood image descriptions

## Security

### API Key Management

- ✅ Use `.env` file (gitignored)
- ✅ Never commit keys to git
- ✅ Rotate keys regularly
- ✅ Use environment-specific keys

### Data Privacy

- ✅ Anonymize customer data in logs
- ✅ Don't send PII to LLM unless necessary
- ✅ Comply with GDPR/privacy regulations

## Troubleshooting

### Common Issues

**1. Module Not Found: 'openai'**
```bash
pip install openai
```

**2. API Key Error**
```bash
# Check .env file
cat .env | grep OPENAI_API_KEY

# Verify loading
python -c "from config.settings import get_settings; print(get_settings().openai_api_key)"
```

**3. Rate Limit Errors**
- Implement exponential backoff
- Use lower-tier model for testing
- Contact OpenAI for limit increase

**4. Timeout Errors**
```python
# Increase timeout
llm = LLMService()
llm.client.timeout = 60.0  # seconds
```

## Migration Guide

### From State-Based to LLM-Enhanced

**Before**:
```python
class Henk1Agent(BaseAgent):
    async def process(self, state):
        if state.customer.customer_id:
            return AgentDecision(next_agent="design_henk")
        return AgentDecision(next_agent="henk1")
```

**After**:
```python
from agents.llm_mixin import LLMMixin

class Henk1Agent(LLMMixin, BaseAgent):
    def __init__(self, enable_llm=True):
        super().__init__(agent_name="henk1", enable_llm=enable_llm)

    async def process(self, state):
        if self.enable_llm:
            # LLM-enhanced decision
            response = await self.make_llm_decision(
                system_prompt=HENK1_SYSTEM_PROMPT,
                state_description=f"Customer: {state.customer.model_dump()}",
            )
            # Parse response and create AgentDecision
            ...
        else:
            # Original state-based logic
            if state.customer.customer_id:
                return AgentDecision(next_agent="design_henk")
            return AgentDecision(next_agent="henk1")
```

## Future Enhancements

### Planned Features

- [ ] Function calling for tool use
- [ ] Streaming responses for UI
- [ ] Multi-language support
- [ ] Voice interaction
- [ ] Fine-tuned models per agent
- [ ] A/B testing framework

## Support

- **Issues**: https://github.com/Henninglutz/Laserhenk/issues
- **Docs**: `docs/`
- **Examples**: `examples/test_llm_integration.py`
