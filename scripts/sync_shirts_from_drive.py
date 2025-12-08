"""
Sync Shirt Catalog and RAG Chunks from Google Drive

Lädt beide Dateien von Google Drive herunter:
1. shirt_catalog.json - Hemden-Katalog mit 72SH, 70SH, 73SH, 74SH Stoffen
2. rag_shirts_chunk.jsonl - RAG-Chunks für Hemden

Usage:
    python scripts/sync_shirts_from_drive.py
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
        "   Installiere mit: pip install google-auth google-auth-oauthlib "
        "google-auth-httplib2 google-api-python-client"
    )
    sys.exit(1)

# Load environment
load_dotenv()

# Configuration
CREDENTIALS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv(
    "GOOGLE_DRIVE_CREDENTIALS_PATH"
)
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Files to sync
FILES_TO_SYNC = [
    {
        "name": "shirt_catalog.json",
        "output": "drive_mirror/henk/shirts/shirt_catalog.json",
        "required": True,
    },
    {
        "name": "rag_shirts_chunk.jsonl",
        "output": "drive_mirror/henk/shirts/rag_shirts_chunk.jsonl",
        "required": False,
    },
]

# Scopes
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def authenticate():
    """Authenticate with Google Drive API using Service Account."""
    if not CREDENTIALS_FILE:
        print("❌ GOOGLE_DRIVE_CREDENTIALS_PATH nicht in .env gesetzt")
        print("\nSetze in .env:")
        print("GOOGLE_DRIVE_CREDENTIALS_PATH=./credentials/google_drive_credentials.json")
        print("GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here")
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"❌ Credentials Datei nicht gefunden: {CREDENTIALS_FILE}")
        sys.exit(1)

    if not FOLDER_ID:
        print("❌ GOOGLE_DRIVE_FOLDER_ID nicht in .env gesetzt")
        sys.exit(1)

    print(f"✅ Lade Credentials von: {CREDENTIALS_FILE}")
    print(f"📁 Google Drive Folder ID: {FOLDER_ID}")

    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )

    service = build("drive", "v3", credentials=credentials)
    return service


def search_file_recursive(service, filename, folder_id=None):
    """
    Search for a file in Google Drive, recursively searching subfolders.

    Args:
        service: Google Drive API service
        filename: Name of file to search for
        folder_id: Optional folder ID to start search

    Returns:
        File metadata dict or None
    """
    # Search in current folder
    if folder_id:
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    else:
        query = f"name='{filename}' and trashed=false"

    print(f"🔍 Suche nach '{filename}'...")

    results = (
        service.files()
        .list(q=query, spaces="drive", fields="files(id, name, mimeType, webViewLink)")
        .execute()
    )

    files = results.get("files", [])

    if files:
        file = files[0]
        print(f"✅ Gefunden: {file['name']}")
        print(f"   ID: {file['id']}")
        print(f"   Link: {file.get('webViewLink', 'N/A')}")
        return file

    # If not found and folder_id specified, search in subfolders
    if folder_id:
        print(f"   → Suche in Unterordnern...")
        subfolders_query = (
            f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )

        subfolders = (
            service.files()
            .list(q=subfolders_query, spaces="drive", fields="files(id, name)")
            .execute()
        )

        for subfolder in subfolders.get("files", []):
            print(f"   → Prüfe Ordner: {subfolder['name']}")
            result = search_file_recursive(service, filename, subfolder["id"])
            if result:
                return result

    return None


def download_file(service, file_id, output_path):
    """Download a file from Google Drive."""
    request = service.files().get_media(fileId=file_id)

    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    print(f"📥 Lade herunter nach: {output_path}")

    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"   Download {int(status.progress() * 100)}% complete")

    # Write to file
    with open(output_path, "wb") as f:
        f.write(fh.getvalue())

    fh.close()
    print("✅ Download complete!")

    # Analyze file
    if output_path.endswith(".json"):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            print("\n📊 Datei-Analyse:")
            print(f"   Type: {type(data)}")

            if isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
                if "meta" in data:
                    print(f"   Meta: {data['meta']}")
                if "fabrics" in data:
                    if isinstance(data["fabrics"], dict):
                        print(f"   Fabric Series: {list(data['fabrics'].keys())}")
                    elif isinstance(data["fabrics"], list):
                        print(f"   Fabrics Count: {len(data['fabrics'])}")

            elif isinstance(data, list):
                print(f"   Items: {len(data)}")
                if data:
                    print(f"   First item keys: {list(data[0].keys())}")

        except Exception as e:
            print(f"   ⚠️  Konnte JSON nicht analysieren: {e}")

    elif output_path.endswith(".jsonl"):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            print("\n📊 Datei-Analyse:")
            print(f"   Lines: {len(lines)}")

            if lines:
                first_item = json.loads(lines[0])
                print(f"   First item keys: {list(first_item.keys())}")

        except Exception as e:
            print(f"   ⚠️  Konnte JSONL nicht analysieren: {e}")


def main():
    """Main sync function."""
    print("=" * 70)
    print("📥 SYNC SHIRT CATALOG FROM GOOGLE DRIVE")
    print("=" * 70)
    print()

    # Authenticate
    service = authenticate()
    print()

    # Sync each file
    results = {"success": [], "failed": [], "skipped": []}

    for file_config in FILES_TO_SYNC:
        filename = file_config["name"]
        output_path = file_config["output"]
        required = file_config["required"]

        print("\n" + "=" * 70)
        print(f"📄 Datei: {filename}")
        print("=" * 70)

        # Search for file
        file_info = search_file_recursive(service, filename, FOLDER_ID)

        if not file_info:
            if required:
                print(f"❌ ERFORDERLICHE Datei nicht gefunden: {filename}")
                results["failed"].append(filename)
            else:
                print(f"⚠️  Optionale Datei nicht gefunden: {filename}")
                results["skipped"].append(filename)
            continue

        # Download file
        try:
            download_file(service, file_info["id"], output_path)
            results["success"].append(filename)
        except Exception as e:
            print(f"❌ Fehler beim Download: {e}")
            results["failed"].append(filename)

    # Summary
    print("\n" + "=" * 70)
    print("📊 ZUSAMMENFASSUNG")
    print("=" * 70)
    print(f"\n✅ Erfolgreich: {len(results['success'])}")
    for f in results["success"]:
        print(f"   - {f}")

    if results["failed"]:
        print(f"\n❌ Fehlgeschlagen: {len(results['failed'])}")
        for f in results["failed"]:
            print(f"   - {f}")

    if results["skipped"]:
        print(f"\nℹ️  Übersprungen: {len(results['skipped'])}")
        for f in results["skipped"]:
            print(f"   - {f}")

    print("\n" + "=" * 70)

    if results["failed"]:
        print("⚠️  Einige Dateien konnten nicht heruntergeladen werden!")
        sys.exit(1)
    else:
        print("✅ Alle Dateien erfolgreich synchronisiert!")


if __name__ == "__main__":
    main()
