"""
Import scraped Formens fabric data to PostgreSQL database.

This script reads the formens_fabrics.json file created by scrape_formens_b2b.py
and imports all fabrics into the PostgreSQL fabrics table for RAG use.

Usage:
    python scripts/import_formens_to_db.py

    # Or specify custom paths:
    python scripts/import_formens_to_db.py --input storage/fabrics/formens_fabrics.json
"""

import asyncio
import asyncpg
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional


async def import_formens_fabrics(conn, json_path: Path):
    """
    Import Formens fabrics from JSON into PostgreSQL database.

    Strategy:
    1. Load all fabrics from JSON
    2. For each fabric, check if it exists by URL or code
    3. If exists: UPDATE with new data
    4. If not: INSERT as new fabric
    """
    print(f"📂 Loading Formens fabric data from: {json_path}")

    if not json_path.exists():
        print(f"❌ File not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fabrics = data.get('fabrics', [])
    source_url = data.get('source', 'https://b2b2.formens.ro')
    scraped_at = data.get('scraped_at', '')

    print(f"✓ Loaded {len(fabrics)} fabrics from JSON")
    print(f"  Source: {source_url}")
    print(f"  Scraped at: {scraped_at}")
    print()

    # Check current DB state
    db_count = await conn.fetchval("SELECT COUNT(*) FROM fabrics")
    print(f"📊 Current fabrics in database: {db_count}")

    formens_count = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fabrics
        WHERE additional_metadata::text LIKE '%formens%'
           OR supplier ILIKE '%formens%'
    """)
    print(f"   - Existing Formens fabrics: {formens_count}")
    print()

    # Process each fabric
    inserted = 0
    updated = 0
    skipped = 0
    errors = 0

    for i, fabric in enumerate(fabrics, 1):
        try:
            code = fabric.get('code', '')
            name = fabric.get('name', '')
            url = fabric.get('url', '')
            image_url = fabric.get('image_url')
            image_path = fabric.get('image_path')
            price_category = fabric.get('price_category')
            composition = fabric.get('composition')
            weight = fabric.get('weight')
            origin = fabric.get('origin')
            description = fabric.get('description')
            extra = fabric.get('extra', {})

            if not code and not url:
                print(f"  ⚠️  Skipping fabric without code or URL (index {i})")
                skipped += 1
                continue

            # Try to find existing fabric by code or URL
            existing = await conn.fetchrow("""
                SELECT id, fabric_code, name
                FROM fabrics
                WHERE fabric_code = $1
                   OR (additional_metadata->>'source_url' = $2 AND $2 != '')
                LIMIT 1
            """, code, url)

            # Build additional_metadata
            metadata = {
                'source': 'Formens B2B',
                'source_url': url,
                'scraped_at': fabric.get('scraped_at', scraped_at),
                'image_url': image_url,
                'image_path': image_path,
            }
            if extra:
                metadata.update(extra)

            if existing:
                # Update existing fabric
                await conn.execute("""
                    UPDATE fabrics
                    SET
                        name = COALESCE($2, name),
                        composition = COALESCE($3, composition),
                        weight = COALESCE($4, weight),
                        origin = COALESCE($5, origin),
                        description = COALESCE($6, description),
                        supplier = COALESCE($7, supplier),
                        category = COALESCE($8, category),
                        additional_metadata = COALESCE(
                            additional_metadata::jsonb || $9::jsonb,
                            $9::jsonb
                        ),
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    existing['id'],
                    name or None,
                    composition,
                    weight,
                    origin,
                    description,
                    'Formens',
                    price_category,
                    json.dumps(metadata)
                )
                updated += 1
                if updated % 50 == 0:
                    print(f"  ⟳ Updated {updated} fabrics...")
            else:
                # Insert new fabric
                await conn.execute("""
                    INSERT INTO fabrics (
                        fabric_code, name, composition, weight, origin,
                        description, supplier, category, additional_metadata,
                        created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                """,
                    code or f"formens_{i}",
                    name or f"Formens Fabric {code or i}",
                    composition,
                    weight,
                    origin,
                    description,
                    'Formens',
                    price_category,
                    json.dumps(metadata)
                )
                inserted += 1
                if inserted % 50 == 0:
                    print(f"  ➕ Inserted {inserted} new fabrics...")

        except Exception as exc:
            print(f"  ❌ Error processing fabric {i} ({code}): {exc}")
            errors += 1
            continue

    print()
    print("=" * 80)
    print("IMPORT COMPLETE")
    print("=" * 80)
    print(f"✓ Inserted: {inserted} new fabrics")
    print(f"✓ Updated: {updated} existing fabrics")
    if skipped > 0:
        print(f"⚠️  Skipped: {skipped} fabrics")
    if errors > 0:
        print(f"❌ Errors: {errors} fabrics")
    print()

    # Show final stats
    final_count = await conn.fetchval("SELECT COUNT(*) FROM fabrics")
    final_formens = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fabrics
        WHERE additional_metadata::text LIKE '%formens%'
           OR supplier ILIKE '%formens%'
    """)

    print(f"📊 Final database state:")
    print(f"   Total fabrics: {final_count}")
    print(f"   Formens fabrics: {final_formens}")
    print()


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Import Formens fabric data to PostgreSQL"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("storage/fabrics/formens_fabrics.json"),
        help="Path to the scraped JSON file",
    )
    args = parser.parse_args()

    # Get database connection
    db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_CONNECTION_STRING')
    if not db_url:
        print("❌ DATABASE_URL or POSTGRES_CONNECTION_STRING not set!")
        print()
        print("Please set one of these environment variables:")
        print("  export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        print("  export POSTGRES_CONNECTION_STRING='postgresql://user:pass@host:port/dbname'")
        return

    # Convert to asyncpg format
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql://', 1)
    elif db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    db_url = db_url.replace('+asyncpg', '')

    try:
        print("=" * 80)
        print("IMPORTING FORMENS FABRICS TO DATABASE")
        print("=" * 80)
        print()

        conn = await asyncpg.connect(db_url)
        print(f"✅ Connected to database")
        print()

        await import_formens_fabrics(conn, args.input)

        await conn.close()

        print("✅ Import successful!")
        print()
        print("💡 Next steps:")
        print("   1. Regenerate embeddings for RAG:")
        print("      python scripts/generate_embeddings.py")
        print()
        print("   2. Test RAG queries:")
        print("      'Zeig mir Stoffe von Formens'")
        print("      'Welche Stoffe haben 100% Wolle?'")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
