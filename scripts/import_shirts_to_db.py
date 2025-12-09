"""
Import Shirt Fabrics from shirt_catalog.json to Database

Importiert Hemden-Stoffe (72SH, 70SH, 73SH, 74SH) in die fabrics Tabelle.

Usage:
    python scripts/import_shirts_to_db.py
"""

import asyncio
import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
SHIRT_CATALOG_PATH = "drive_mirror/henk/shirts/shirt_catalog.json"


async def import_shirt_fabrics():
    """Import shirt fabrics from JSON to database."""

    # Load JSON
    print(f"📂 Lade {SHIRT_CATALOG_PATH}...")

    if not os.path.exists(SHIRT_CATALOG_PATH):
        print(f"❌ Datei nicht gefunden: {SHIRT_CATALOG_PATH}")
        print("\nFühre zuerst aus:")
        print("python scripts/sync_shirts_from_drive.py")
        return

    with open(SHIRT_CATALOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Analyze structure
    print(f"\n📊 Katalog-Info:")
    if "meta" in data:
        meta = data["meta"]
        print(f"   Name: {meta.get('catalog_name')}")
        print(f"   Version: {meta.get('version')}")
        print(f"   Total Shirts: {meta.get('total_shirts')}")
        print(f"   Fabric Prefixes: {meta.get('fabric_prefixes')}")

    # Extract fabrics
    all_fabrics = []

    if "fabrics" in data:
        fabrics_section = data["fabrics"]

        # Check structure
        if isinstance(fabrics_section, dict):
            # Format: {"72SH_series": {"fabrics": [...]}, ...}
            for series_name, series_data in fabrics_section.items():
                if isinstance(series_data, dict) and "fabrics" in series_data:
                    series_fabrics = series_data["fabrics"]
                    if series_fabrics:  # Not empty
                        all_fabrics.extend(series_fabrics)
                        print(
                            f"\n   {series_name}: {len(series_fabrics)} Stoffe gefunden"
                        )

        elif isinstance(fabrics_section, list):
            # Format: [{"reference": "72SH001", ...}, ...]
            all_fabrics = fabrics_section
            print(f"\n   Fabrics als Liste: {len(all_fabrics)} Stoffe")

    if not all_fabrics:
        print("\n⚠️  Keine Hemden-Stoffe im Katalog gefunden!")
        print("   Prüfe die Struktur von shirt_catalog.json")
        return

    print(f"\n📦 Gesamt gefunden: {len(all_fabrics)} Hemden-Stoffe")

    # Connect to DB
    connection_string = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(connection_string, echo=False)

    print(f"\n🔄 Importiere in Datenbank...")

    async with engine.begin() as conn:
        inserted = 0
        skipped = 0
        errors = 0

        for fabric in all_fabrics:
            try:
                # Extract data
                fabric_code = fabric.get("reference") or fabric.get("fabric_code")

                if not fabric_code:
                    print(f"⚠️  Stoff ohne Referenznummer übersprungen")
                    skipped += 1
                    continue

                # Basic fields
                name = fabric.get("name") or fabric.get("description", "")[:255]
                supplier = fabric.get("supplier")
                composition = fabric.get("composition")
                weight = fabric.get("weight")
                color = fabric.get("color")
                pattern = fabric.get("pattern")

                # Category - extract from CAT field
                cat_raw = fabric.get("cat") or fabric.get("category")
                category = cat_raw

                # Price category
                price_category = None
                if cat_raw and "CAT" in str(cat_raw).upper():
                    # Extract number from "CAT 5" -> "5"
                    try:
                        price_category = "".join(
                            filter(str.isdigit, str(cat_raw))
                        )
                    except:
                        pass

                # Additional metadata
                additional_metadata = {
                    "fabric_type": "shirt",
                    "series": fabric.get("series"),
                    "price_tier": fabric.get("price_tier"),
                }

                # Remove None values
                additional_metadata = {
                    k: v for k, v in additional_metadata.items() if v is not None
                }

                # Insert
                query = text(
                    """
                    INSERT INTO fabrics (
                        fabric_code, name, supplier, composition, weight,
                        color, pattern, category, price_category,
                        additional_metadata
                    ) VALUES (
                        :fabric_code, :name, :supplier, :composition, :weight,
                        :color, :pattern, :category, :price_category,
                        :metadata::jsonb
                    )
                    ON CONFLICT (fabric_code) DO UPDATE SET
                        name = EXCLUDED.name,
                        supplier = EXCLUDED.supplier,
                        composition = EXCLUDED.composition,
                        weight = EXCLUDED.weight,
                        color = EXCLUDED.color,
                        pattern = EXCLUDED.pattern,
                        category = EXCLUDED.category,
                        price_category = EXCLUDED.price_category,
                        additional_metadata = EXCLUDED.additional_metadata,
                        updated_at = NOW()
                    RETURNING id
                """
                )

                result = await conn.execute(
                    query,
                    {
                        "fabric_code": fabric_code,
                        "name": name,
                        "supplier": supplier,
                        "composition": composition,
                        "weight": weight,
                        "color": color,
                        "pattern": pattern,
                        "category": category,
                        "price_category": price_category,
                        "metadata": json.dumps(additional_metadata),
                    },
                )

                if result.rowcount > 0:
                    inserted += 1
                    if inserted % 50 == 0:
                        print(f"   → {inserted} Stoffe importiert...")
                else:
                    skipped += 1

            except Exception as e:
                print(f"❌ Fehler bei {fabric.get('reference', 'unknown')}: {e}")
                errors += 1

        print(f"\n✅ Import abgeschlossen!")
        print(f"   Eingefügt/Aktualisiert: {inserted}")
        print(f"   Übersprungen: {skipped}")
        if errors > 0:
            print(f"   ⚠️  Fehler: {errors}")

    await engine.dispose()

    # Next steps
    if inserted > 0:
        print("\n" + "=" * 70)
        print("🎯 NÄCHSTE SCHRITTE")
        print("=" * 70)
        print("\n1. Embeddings für Hemden-Stoffe generieren:")
        print("   python scripts/generate_fabric_embeddings.py --batch-size 50")
        print("\n2. Embeddings verifizieren:")
        print("   python scripts/verify_embeddings.py")
        print("\n3. RAG-System testen:")
        print("   python scripts/test_rag_fabric_search.py")


if __name__ == "__main__":
    asyncio.run(import_shirt_fabrics())
