"""
Import scraped fabric data from storage/fabrics2.json to PostgreSQL

This script handles the 1988+ fabrics from the henk.bettercallhenk.de scraper.

Usage:
    python scripts/import_scraped_fabrics.py --source storage/fabrics2.json
"""

import asyncio
import asyncpg
import argparse
import json
import os
import re
from pathlib import Path
from datetime import datetime


def parse_weight(weight_str: str) -> int:
    """
    Parse weight string to integer.

    Examples:
        '250g/m²' -> 250
        '280 g/m²' -> 280
        '320gr/m' -> 320
        None -> None
    """
    if not weight_str:
        return None

    # Extract digits from weight string
    match = re.search(r'(\d+)', str(weight_str))
    if match:
        return int(match.group(1))

    return None


async def import_scraped_fabrics(conn, json_path: Path):
    """
    Import fabrics from scraper JSON into database.

    JSON structure expected:
    {
        "meta": {
            "source": "Internal Catalog",
            "scraped_at": "2025-11-21T18:08:03.649723",
            "total_fabrics": 2256
        },
        "fabrics": [
            {
                "fabric_code": "70SH2109",
                "name": "...",
                "composition": "100% Schurwolle",
                "weight": "250g/m²",
                "color": "Navy",
                "pattern": "Uni",
                ...
            }
        ]
    }
    """
    print(f"📂 Loading fabric data from: {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fabrics = data.get('fabrics', [])
    meta = data.get('meta', {})

    print(f"✓ Loaded {len(fabrics)} fabrics from JSON")
    print(f"  Source: {meta.get('source', 'Unknown')}")
    print(f"  Scraped at: {meta.get('scraped_at', 'Unknown')}")
    print()

    # Check current DB state
    db_count = await conn.fetchval("SELECT COUNT(*) FROM fabrics")
    print(f"📊 Current fabrics in database: {db_count}")
    print()

    # Process each fabric
    inserted = 0
    updated = 0
    errors = 0

    for i, fabric in enumerate(fabrics, 1):
        fabric_code = fabric.get('fabric_code') or fabric.get('reference')

        if not fabric_code:
            print(f"  ⚠️  Skipping fabric {i}: No fabric_code")
            errors += 1
            continue

        # Parse weight (convert "250g/m²" to 250)
        weight_str = fabric.get('weight')
        weight_int = parse_weight(weight_str)

        # Check if fabric exists
        existing = await conn.fetchrow("""
            SELECT id FROM fabrics
            WHERE fabric_code = $1
        """, fabric_code)

        try:
            if existing:
                # Update existing fabric
                await conn.execute("""
                    UPDATE fabrics
                    SET
                        name = COALESCE($2, name),
                        composition = COALESCE($3, composition),
                        weight = COALESCE($4, weight),
                        color = COALESCE($5, color),
                        pattern = COALESCE($6, pattern),
                        category = COALESCE($7, category),
                        stock_status = COALESCE($8, stock_status),
                        supplier = COALESCE($9, supplier),
                        origin = COALESCE($10, origin),
                        description = COALESCE($11, description),
                        care_instructions = COALESCE($12, care_instructions),
                        additional_metadata = COALESCE(
                            additional_metadata::jsonb || $13::jsonb,
                            $13::jsonb
                        ),
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    existing['id'],
                    fabric.get('name'),
                    fabric.get('composition'),
                    weight_int,  # Parsed integer
                    fabric.get('color'),
                    fabric.get('pattern'),
                    fabric.get('category'),
                    fabric.get('stock_status') or 'in_stock',
                    fabric.get('supplier'),
                    fabric.get('origin'),
                    fabric.get('description'),
                    fabric.get('care_instructions'),
                    json.dumps({
                        'weight_original': weight_str,  # Keep original with unit
                        'scraped_at': meta.get('scraped_at'),
                        'source': 'henk.bettercallhenk.de scraper',
                        'season': fabric.get('season'),
                        'occasion': fabric.get('occasion'),
                    })
                )
                updated += 1

            else:
                # Insert new fabric
                await conn.execute("""
                    INSERT INTO fabrics (
                        fabric_code, name, composition, weight, color, pattern,
                        category, stock_status, supplier, origin,
                        description, care_instructions, additional_metadata,
                        created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW(), NOW())
                """,
                    fabric_code,
                    fabric.get('name') or f"Stoff {fabric_code}",
                    fabric.get('composition'),
                    weight_int,  # Parsed integer
                    fabric.get('color'),
                    fabric.get('pattern'),
                    fabric.get('category'),
                    fabric.get('stock_status') or 'in_stock',
                    fabric.get('supplier'),
                    fabric.get('origin'),
                    fabric.get('description'),
                    fabric.get('care_instructions'),
                    json.dumps({
                        'weight_original': weight_str,  # Keep original with unit
                        'scraped_at': meta.get('scraped_at'),
                        'source': 'henk.bettercallhenk.de scraper',
                        'season': fabric.get('season'),
                        'occasion': fabric.get('occasion'),
                    })
                )
                inserted += 1

            # Progress update
            if i % 100 == 0:
                print(f"  ✓ Processed {i}/{len(fabrics)} fabrics... ({updated} updated, {inserted} inserted, {errors} errors)")

        except Exception as e:
            print(f"  ❌ Error processing fabric {i} ({fabric_code}): {e}")
            errors += 1

    print()
    print("=" * 80)
    print("IMPORT COMPLETE")
    print("=" * 80)
    print(f"✓ Updated: {updated} existing fabrics")
    print(f"✓ Inserted: {inserted} new fabrics")
    if errors > 0:
        print(f"❌ Errors: {errors} fabrics")
    print()

    # Show final stats
    final_count = await conn.fetchval("SELECT COUNT(*) FROM fabrics")
    final_with_data = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fabrics
        WHERE composition IS NOT NULL
           OR color IS NOT NULL
           OR pattern IS NOT NULL
    """)

    print(f"📊 Final database state:")
    print(f"   Total fabrics: {final_count}")
    print(f"   With metadata: {final_with_data} ({final_with_data/final_count*100:.1f}%)")
    print()


async def main():
    parser = argparse.ArgumentParser(description='Import scraped fabric data to database')
    parser.add_argument('--source', type=str, default='storage/fabrics2.json',
                       help='Path to scraped fabrics JSON file')

    args = parser.parse_args()

    # Get database connection string
    db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_CONNECTION_STRING')
    if not db_url:
        print("❌ DATABASE_URL or POSTGRES_CONNECTION_STRING not set!")
        return

    # Convert to asyncpg format
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql://', 1)
    elif db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)

    db_url = db_url.replace('+asyncpg', '')

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"❌ Source file not found: {source_path}")
        print()
        print("Expected location:")
        print(f"  {source_path.absolute()}")
        return

    try:
        print("=" * 80)
        print("IMPORTING FABRICS TO DATABASE")
        print("=" * 80)
        print()

        conn = await asyncpg.connect(db_url)
        print(f"✅ Connected to database")
        print()

        await import_scraped_fabrics(conn, source_path)

        await conn.close()

        print("✅ Import successful!")
        print()
        print("💡 Next steps:")
        print("   1. Generate embeddings: python scripts/generate_fabric_embeddings.py")
        print("   2. Test RAG tool in browser: 'zeig mir Stoffe'")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
