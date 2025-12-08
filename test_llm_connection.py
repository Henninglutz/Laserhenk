"""
Schneller Test: Ist HENK LLM erreichbar und antwortet ohne Fehler?
"""
import asyncio
import os
from dotenv import load_dotenv

# Lade .env
load_dotenv()

async def test_llm_connection():
    """Teste ob LLM erreichbar ist und ohne Fehler antwortet."""
    
    print("=" * 70)
    print("🧪 HENK LLM VERBINDUNGSTEST")
    print("=" * 70)
    print()
    
    # 1. Prüfe Umgebungsvariablen
    print("1️⃣ Prüfe Konfiguration...")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_key:
        print("   ❌ OPENAI_API_KEY nicht in .env gefunden")
        print("   💡 Bitte .env Datei erstellen: cp .env.example .env")
        return False
    
    print(f"   ✅ OPENAI_API_KEY gefunden: {openai_key[:10]}...")
    print()
    
    # 2. Teste OpenAI Verbindung
    print("2️⃣ Teste OpenAI API Verbindung...")
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=openai_key)
        
        # Einfache Test-Anfrage
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Hallo, bist du erreichbar? Antworte nur mit 'Ja'."}
            ],
            max_tokens=10
        )
        
        answer = response.choices[0].message.content
        print(f"   ✅ OpenAI API erreichbar")
        print(f"   📝 Antwort: {answer}")
        print()
        
    except Exception as e:
        print(f"   ❌ OpenAI API Fehler: {e}")
        return False
    
    # 3. Teste HENK1 Agent
    print("3️⃣ Teste HENK1 Agent...")
    try:
        from agents.henk1 import Henk1Agent
        from models.graph_state import SessionState
        from models.customer import Customer
        
        # Erstelle minimalen Session-State
        customer = Customer(customer_id="test_123")
        session_state = SessionState(
            session_id="test_session",
            customer=customer,
            messages=[
                {"role": "user", "content": "Hallo HENK, kannst du mich hören?"}
            ]
        )
        
        # Initialisiere Agent
        agent = Henk1Agent()
        print(f"   ✅ HENK1 Agent initialisiert")
        
        # Verarbeite Anfrage
        print(f"   🤔 HENK1 verarbeitet Anfrage...")
        decision = await agent.process(session_state)
        
        print(f"   ✅ HENK1 hat geantwortet!")
        print()
        print(f"   📝 Antwort: {decision.message}")
        print(f"   🎯 Nächster Agent: {decision.next_agent}")
        print(f"   🔧 Action: {decision.action}")
        print()
        
    except Exception as e:
        print(f"   ❌ HENK1 Agent Fehler: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. Zusammenfassung
    print("=" * 70)
    print("✅ ALLE TESTS ERFOLGREICH!")
    print("=" * 70)
    print()
    print("💡 HENK ist erreichbar und antwortet ohne Fehler.")
    print("   Sie können jetzt den vollständigen Workflow testen:")
    print("   → python tests/test_workflow.py")
    print()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_llm_connection())
    exit(0 if success else 1)
