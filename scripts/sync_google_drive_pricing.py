"""
Sync Pricing Data from Google Drive

Lädt die price_book_by_tier.json von Google Drive herunter und analysiert sie.
Nutzt Google Service Account Credentials.

Usage:
    python scripts/sync_google_drive_pricing.py
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
except ImportError:
    print("❌ Google API Bibliotheken fehlen!")
    print(
        "   Installiere mit: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )
    sys.exit(1)

# Load environment
load_dotenv()

# Configuration
CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
FOLDER_ID = os.getenv("GOOGLE_DRIVE_PROMPTS_FOLDER_ID")
TARGET_FILE = "price_book_by_tier.json"
OUTPUT_PATH = "drive_mirror/henk/fabrics/price_book_by_tier.json"

# Scopes
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def authenticate():
    """Authenticate with Google Drive API using Service Account."""
    if not CREDENTIALS_FILE:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS nicht in .env gesetzt")
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Credentials Datei nicht gefunden: {CREDENTIALS_FILE}")
        sys.exit(1)

    print(f"✅ Lade Credentials von: {CREDENTIALS_FILE}")

    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)
    return service


def find_file_in_folder(service, folder_id, filename):
    """Find a file by name in a specific folder."""
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"

    print(f"🔍 Suche nach '{filename}' in Folder {folder_id}...")

    results = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, modifiedTime, size)",
        )
        .execute()
    )

    files = results.get("files", [])

    if not files:
        print(f"❌ Datei '{filename}' nicht gefunden in Folder {folder_id}")
        return None

    file = files[0]
    print(f"✅ Gefunden: {file['name']}")
    print(f"   ID: {file['id']}")
    print(f"   Type: {file['mimeType']}")
    print(f"   Modified: {file.get('modifiedTime', 'unknown')}")
    print(f"   Size: {file.get('size', 'unknown')} bytes")

    return file


def download_file(service, file_id, output_path):
    """Download a file from Google Drive."""
    request = service.files().get_media(fileId=file_id)

    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fh = io.FileIO(output_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)

    print(f"📥 Downloading to {output_path}...")

    done = False
    while done is False:
        status, done = downloader.next_chunk()
        if status:
            print(f"   Progress: {int(status.progress() * 100)}%")

    fh.close()
    print("✅ Download complete!")


def analyze_pricing_file(file_path):
    """Analyze the pricing JSON file."""
    print(f"\n📊 ANALYSE: {file_path}")
    print("=" * 70)

    if not os.path.exists(file_path):
        print(f"❌ Datei nicht gefunden: {file_path}")
        return

    file_size = os.path.getsize(file_path)
    print(f"Dateigröße: {file_size} bytes")

    if file_size == 0:
        print("⚠️  Datei ist leer!")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print("✅ JSON geladen")
        print("\nStruktur:")
        print(f"  Type: {type(data)}")

        if isinstance(data, dict):
            print(f"  Keys: {list(data.keys())[:10]}")
            print(f"  Anzahl Einträge: {len(data)}")

            # Show first entry
            if data:
                first_key = list(data.keys())[0]
                print(f"\n📄 Beispiel-Eintrag ('{first_key}'):")
                print(json.dumps(data[first_key], indent=2)[:500])

        elif isinstance(data, list):
            print(f"  Anzahl Einträge: {len(data)}")

            if data:
                print("\n📄 Erstes Element:")
                print(json.dumps(data[0], indent=2)[:500])

        print("\n" + "=" * 70)
        return data

    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print("\nErste 200 Zeichen:")
        with open(file_path, "r") as f:
            print(f.read(200))
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main execution."""
    print("=" * 70)
    print("🔄 GOOGLE DRIVE PRICING SYNC")
    print("=" * 70)

    # Authenticate
    service = authenticate()

    # Find file
    file = find_file_in_folder(service, FOLDER_ID, TARGET_FILE)

    if not file:
        # Try to list all files in folder
        print(f"\n📋 Dateien im Folder {FOLDER_ID}:")
        results = (
            service.files()
            .list(
                q=f"'{FOLDER_ID}' in parents and trashed=false",
                spaces="drive",
                fields="files(id, name, mimeType)",
            )
            .execute()
        )

        for f in results.get("files", []):
            print(f"  - {f['name']} ({f['mimeType']})")

        sys.exit(1)

    # Download
    download_file(service, file["id"], OUTPUT_PATH)

    # Analyze
    analyze_pricing_file(OUTPUT_PATH)

    print("\n✅ SYNC COMPLETE")
    print(f"   Datei gespeichert: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
