#!/usr/bin/env python3
"""
Demo: Flask App mit Beta-User und Pipedrive Integration

Dieses Script zeigt, wie du das neue Flask-System nutzen kannst:
1. User Registration (als Beta-User)
2. Login und JWT Token erhalten
3. Chat mit dem AI Agent
4. CRM Deal Historie abrufen (Beta-User Feature)
5. Lead in Pipedrive erstellen
"""

import requests
import json
from typing import Optional


class LaserHenkClient:
    """Client für LASERHENK Flask API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.session_id: Optional[str] = None

    def _headers(self, auth: bool = False) -> dict:
        """Generiere Request Headers."""
        headers = {"Content-Type": "application/json"}
        if auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def health_check(self) -> dict:
        """Prüfe Server Status."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()

    def register(self, email: str, username: str, password: str, is_beta_user: bool = False) -> dict:
        """Registriere neuen User."""
        data = {
            "email": email,
            "username": username,
            "password": password,
            "is_beta_user": is_beta_user,
        }
        response = requests.post(
            f"{self.base_url}/api/auth/register",
            headers=self._headers(),
            json=data,
        )
        result = response.json()

        if response.status_code == 201:
            self.access_token = result.get("access_token")
            print(f"✅ Registrierung erfolgreich!")
            print(f"   User: {result['user']['username']}")
            print(f"   Beta-User: {result['user']['is_beta_user']}")

        return result

    def login(self, email: str, password: str) -> dict:
        """Login mit Email und Passwort."""
        data = {"email": email, "password": password}
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            headers=self._headers(),
            json=data,
        )
        result = response.json()

        if response.status_code == 200:
            self.access_token = result.get("access_token")
            print(f"✅ Login erfolgreich!")
            print(f"   User: {result['username']}")
            print(f"   Beta-User: {result['is_beta_user']}")

        return result

    def get_me(self) -> dict:
        """Hole aktuelle User Info."""
        response = requests.get(
            f"{self.base_url}/api/auth/me",
            headers=self._headers(auth=True),
        )
        return response.json()

    def create_session(self) -> dict:
        """Erstelle neue Chat Session."""
        response = requests.post(
            f"{self.base_url}/api/session",
            headers=self._headers(auth=True),
        )
        result = response.json()

        if response.status_code == 201:
            self.session_id = result.get("session_id")
            print(f"✅ Session erstellt: {self.session_id}")

        return result

    def chat(self, message: str) -> dict:
        """Sende Nachricht an AI Agent."""
        if not self.session_id:
            self.create_session()

        data = {
            "message": message,
            "session_id": self.session_id,
        }
        response = requests.post(
            f"{self.base_url}/api/chat",
            headers=self._headers(auth=True),
            json=data,
        )
        result = response.json()

        if response.status_code == 200:
            print(f"\n💬 Du: {message}")
            print(f"🤖 HENK: {result['reply']}")
            print(f"   Stage: {result['stage']}")

        return result

    def create_lead(self, name: str, email: str, phone: Optional[str] = None,
                    deal_title: Optional[str] = None, deal_value: float = 0) -> dict:
        """Erstelle Lead in Pipedrive."""
        data = {
            "name": name,
            "email": email,
            "phone": phone,
            "deal_title": deal_title,
            "deal_value": deal_value,
        }
        response = requests.post(
            f"{self.base_url}/api/crm/lead",
            headers=self._headers(auth=True),
            json=data,
        )
        result = response.json()

        if response.status_code == 201:
            print(f"✅ Lead erstellt in Pipedrive!")
            print(f"   Person ID: {result['person_id']}")
            if result.get('deal_id'):
                print(f"   Deal ID: {result['deal_id']}")

        return result

    def get_deals(self, email: Optional[str] = None) -> dict:
        """Hole Deal-Historie (Beta-User only)."""
        params = {}
        if email:
            params["email"] = email

        response = requests.get(
            f"{self.base_url}/api/crm/deals",
            headers=self._headers(auth=True),
            params=params,
        )
        result = response.json()

        if response.status_code == 200:
            print(f"\n📊 Deal-Historie ({result['count']} Deals):")
            for deal in result['deals']:
                print(f"   • {deal['title']} - {deal['value']} {deal['currency']}")
                print(f"     Status: {deal['status']}, Person: {deal.get('person_name', 'N/A')}")

        return result

    def list_sessions(self) -> dict:
        """Liste alle User Sessions."""
        response = requests.get(
            f"{self.base_url}/api/sessions",
            headers=self._headers(auth=True),
        )
        result = response.json()

        if response.status_code == 200:
            print(f"\n📋 Deine Sessions ({len(result['sessions'])}):")
            for session in result['sessions']:
                print(f"   • {session['session_id'][:16]}... - {session['message_count']} Nachrichten")

        return result


def demo_scenario_1_beta_user():
    """Demo: Beta-User mit vollem Zugriff."""
    print("=" * 70)
    print("DEMO 1: Beta-User mit Pipedrive CRM Integration")
    print("=" * 70)

    client = LaserHenkClient()

    # 1. Health Check
    print("\n1️⃣  Health Check...")
    health = client.health_check()
    print(f"   Status: {health['status']}")

    # 2. Registrierung als Beta-User
    print("\n2️⃣  Registrierung als Beta-User...")
    client.register(
        email="max.mustermann@example.com",
        username="max_mustermann",
        password="SuperSecure123!",
        is_beta_user=True,  # 🔑 Beta-User = Zugriff auf CRM Features
    )

    # 3. User Info abrufen
    print("\n3️⃣  User Info abrufen...")
    me = client.get_me()
    print(f"   Email: {me['email']}")
    print(f"   Beta-User: {me['is_beta_user']}")

    # 4. Chat Session starten
    print("\n4️⃣  Chat mit HENK starten...")
    client.chat("Hallo! Ich suche einen Business-Anzug in Dunkelblau.")
    client.chat("Ich habe ein Budget von ca. 2000 Euro.")

    # 5. Lead in Pipedrive erstellen
    print("\n5️⃣  Lead in Pipedrive erstellen...")
    client.create_lead(
        name="Max Mustermann",
        email="max.mustermann@example.com",
        phone="+49 170 1234567",
        deal_title="Business-Anzug Dunkelblau",
        deal_value=2000,
    )

    # 6. Deal-Historie abrufen (nur Beta-User!)
    print("\n6️⃣  Deal-Historie abrufen (Beta-Feature)...")
    try:
        client.get_deals(email="max.mustermann@example.com")
    except Exception as e:
        print(f"   ⚠️  {e}")

    # 7. Sessions anzeigen
    print("\n7️⃣  Sessions anzeigen...")
    client.list_sessions()

    print("\n" + "=" * 70)
    print("✅ Demo 1 abgeschlossen!")
    print("=" * 70)


def demo_scenario_2_normal_user():
    """Demo: Normaler User ohne Beta-Features."""
    print("\n" + "=" * 70)
    print("DEMO 2: Normaler User (ohne Beta-Zugriff)")
    print("=" * 70)

    client = LaserHenkClient()

    # 1. Registrierung als normaler User
    print("\n1️⃣  Registrierung als normaler User...")
    client.register(
        email="anna.schmidt@example.com",
        username="anna_schmidt",
        password="SecurePass456!",
        is_beta_user=False,  # Kein Beta-Zugriff
    )

    # 2. Chat Session
    print("\n2️⃣  Chat Session...")
    client.chat("Guten Tag! Ich interessiere mich für einen Anzug zur Hochzeit.")
    client.chat("Welche Stoffe empfehlen Sie für Sommer?")

    # 3. Lead erstellen (geht auch ohne Beta)
    print("\n3️⃣  Lead erstellen...")
    client.create_lead(
        name="Anna Schmidt",
        email="anna.schmidt@example.com",
        deal_title="Hochzeits-Anzug",
        deal_value=1500,
    )

    # 4. Versuch Deal-Historie abzurufen (sollte fehlschlagen)
    print("\n4️⃣  Versuch Deal-Historie abzurufen...")
    try:
        client.get_deals()
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        print("   ℹ️  Deal-Historie ist nur für Beta-User verfügbar!")

    print("\n" + "=" * 70)
    print("✅ Demo 2 abgeschlossen!")
    print("=" * 70)


def demo_scenario_3_anonymous_chat():
    """Demo: Anonymer Chat ohne Login."""
    print("\n" + "=" * 70)
    print("DEMO 3: Anonymer Chat (kein Login erforderlich)")
    print("=" * 70)

    client = LaserHenkClient()

    # 1. Session erstellen (ohne Login)
    print("\n1️⃣  Anonymous Session erstellen...")
    session_data = requests.post(f"{client.base_url}/api/session").json()
    session_id = session_data['session_id']
    print(f"   Session ID: {session_id[:16]}...")

    # 2. Chat ohne Authentication
    print("\n2️⃣  Chat ohne Login...")
    messages = [
        "Hallo! Können Sie mir Infos zu Ihren Stoffen geben?",
        "Was kostet ein maßgeschneiderter Anzug?",
    ]

    for msg in messages:
        response = requests.post(
            f"{client.base_url}/api/chat",
            json={"message": msg, "session_id": session_id},
        ).json()
        print(f"\n   💬 Du: {msg}")
        print(f"   🤖 HENK: {response['reply']}")

    print("\n" + "=" * 70)
    print("✅ Demo 3 abgeschlossen!")
    print("=" * 70)


def main():
    """Hauptprogramm - wähle Demo."""
    print("\n🎯 LASERHENK Flask Demo")
    print("\nWelche Demo möchtest du sehen?")
    print("1️⃣  Beta-User mit CRM Integration")
    print("2️⃣  Normaler User")
    print("3️⃣  Anonymer Chat")
    print("4️⃣  Alle Demos nacheinander")

    choice = input("\nAuswahl (1-4): ").strip()

    if choice == "1":
        demo_scenario_1_beta_user()
    elif choice == "2":
        demo_scenario_2_normal_user()
    elif choice == "3":
        demo_scenario_3_anonymous_chat()
    elif choice == "4":
        demo_scenario_1_beta_user()
        demo_scenario_2_normal_user()
        demo_scenario_3_anonymous_chat()
    else:
        print("Ungültige Auswahl!")


if __name__ == "__main__":
    # Für Testzwecke: Starte mit Demo 3 (anonymous)
    print("\n⚠️  WICHTIG: Flask Server muss laufen auf http://localhost:8000")
    print("   Start mit: python run_flask.py\n")

    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Demo beendet!")
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        print("\nℹ️  Stelle sicher, dass:")
        print("   1. Der Flask Server läuft (python run_flask.py)")
        print("   2. Die .env Datei korrekt konfiguriert ist")
        print("   3. pip install -r requirements.txt ausgeführt wurde")
