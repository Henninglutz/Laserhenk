"""
Import Fabric Data from local JSON catalog to PostgreSQL database.

This script maps the fabric_catalog.json (140 fabrics from MTM Cards PDF)
to the PostgreSQL fabrics table.

Usage:
    python scripts/import_fabric_catalog.py
"""

import asyncio
import asyncpg
import json
import os
import re
from pathlib import Path
from typing import Dict, Any


def extract_fabric_metadata(fabric: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract fabric metadata from catalog entry.

    Parses the 'context' field to extract:
    - Supplier name
    - Product name
    - Composition (material)
    - Weight
    """
    context = fabric.get('context', '')
    reference = fabric.get('reference', '')

    # Parse context: "No. 1 / VITALE BARBERIS / 695.401/18 / Tela Rustica / 100% Virgin Wool, 250 gr/ml / Price: cat. 5 /"
    parts = [p.strip() for p in context.split('/') if p.strip()]

    supplier = None
    product_name = None
    composition = None
    weight = None

    # Common patterns
    for part in parts:
        # Supplier (all caps, 2+ words)
        if part.isupper() and len(part.split()) >= 2 and not supplier:
            supplier = part

        # Composition (contains %)
        elif '%' in part:
            composition = part
            # Extract weight if present
            weight_match = re.search(r'(\d+)\s*gr?/m', part)
            if weight_match:
                weight = weight_match.group(1)

        # Product name (capitalized, not all caps, not a number)
        elif part and part[0].isupper() and not part.isupper() and not part.replace('.', '').isdigit():
            if not product_name:
                product_name = part

    # Fallback: use reference as name
    if not product_name:
        product_name = f"Stoff {reference}"

    return {
        'supplier': supplier,
        'name': product_name,
        'composition': composition,
        'weight': weight,
        'reference': reference,
        'category': fabric.get('cat_raw', ''),
        'tier': fabric.get('tier', ''),
    }


async def import_fabrics_from_catalog(conn, catalog_path: Path):
    """
    Import fabrics from local catalog JSON into database.

    Strategy:
    1. Load all fabrics from JSON
    2. For each fabric, extract metadata
    3. Try to match with existing fabric_code in DB
    4. If match: UPDATE metadata
    5. If no match: INSERT new fabric
    """
    print(f"📂 Loading fabric catalog from: {catalog_path}")

    with open(catalog_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    fabrics = data.get('fabrics', [])
    print(f"✓ Loaded {len(fabrics)} fabrics from catalog")
    print()

    # Check current DB state
    db_count = await conn.fetchval("SELECT COUNT(*) FROM fabrics")
    print(f"📊 Current fabrics in database: {db_count}")

    db_with_data = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fabrics
        WHERE composition IS NOT NULL
    """)
    print(f"   - With composition data: {db_with_data}")
    print()

    # Process each fabric
    inserted = 0
    updated = 0
    skipped = 0

    for i, fabric in enumerate(fabrics, 1):
        metadata = extract_fabric_metadata(fabric)
        reference = metadata['reference']

        # Try to find matching fabric by reference or similar code
        # First attempt: exact match on fabric_code
        existing = await conn.fetchrow("""
            SELECT id, fabric_code
            FROM fabrics
            WHERE fabric_code = $1
        """, reference)

        if existing:
            # Update existing fabric
            await conn.execute("""
                UPDATE fabrics
                SET
                    name = COALESCE($2, name),
                    composition = COALESCE($3, composition),
                    weight = COALESCE($4, weight),
                    supplier = COALESCE($5, supplier),
                    category = COALESCE($6, category),
                    description = COALESCE($7, description),
                    additional_metadata = COALESCE(
                        additional_metadata::jsonb || $8::jsonb,
                        $8::jsonb
                    ),
                    updated_at = NOW()
                WHERE id = $1
            """,
                existing['id'],
                metadata['name'],
                metadata['composition'],
                metadata['weight'],
                metadata['supplier'],
                metadata['category'],
                f"Tier: {metadata['tier']} | Ref: {reference}",
                json.dumps({
                    'tier': metadata['tier'],
                    'reference': reference,
                    'source': 'MTM Cards PDF',
                    'page': fabric.get('page'),
                })
            )
            updated += 1

        else:
            # Insert new fabric
            await conn.execute("""
                INSERT INTO fabrics (
                    fabric_code, name, composition, weight, supplier,
                    category, description, additional_metadata,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
            """,
                reference,  # Use reference as fabric_code
                metadata['name'],
                metadata['composition'],
                metadata['weight'],
                metadata['supplier'],
                metadata['category'],
                f"Tier: {metadata['tier']} | Ref: {reference}",
                json.dumps({
                    'tier': metadata['tier'],
                    'reference': reference,
                    'source': 'MTM Cards PDF',
                    'page': fabric.get('page'),
                    'price_tiers': fabric.get('price_tiers', {}),
                })
            )
            inserted += 1

        # Progress update
        if i % 20 == 0:
            print(f"  ✓ Processed {i}/{len(fabrics)} fabrics...")

    print()
    print("=" * 80)
    print("IMPORT COMPLETE")
    print("=" * 80)
    print(f"✓ Inserted: {inserted} new fabrics")
    print(f"✓ Updated: {updated} existing fabrics")
    if skipped > 0:
        print(f"⚠ Skipped: {skipped} fabrics")
    print()

    # Show final stats
    final_count = await conn.fetchval("SELECT COUNT(*) FROM fabrics")
    final_with_data = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fabrics
        WHERE composition IS NOT NULL
    """)

    print(f"📊 Final database state:")
    print(f"   Total fabrics: {final_count}")
    print(f"   With data: {final_with_data} ({final_with_data/final_count*100:.1f}%)")
    print()


async def main():
    # Find fabric catalog
    catalog_path = Path(__file__).parent.parent / 'drive_mirror' / 'henk' / 'fabrics' / 'fabric_catalog.json'

    if not catalog_path.exists():
        print(f"❌ Fabric catalog not found at: {catalog_path}")
        print()
        print("Expected location:")
        print(f"  {catalog_path}")
        return

    # Get database connection
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

    try:
        print("=" * 80)
        print("IMPORTING FABRIC CATALOG TO DATABASE")
        print("=" * 80)
        print()

        conn = await asyncpg.connect(db_url)
        print(f"✅ Connected to database")
        print()

        await import_fabrics_from_catalog(conn, catalog_path)

        await conn.close()

        print("✅ Import successful!")
        print()
        print("💡 Next steps:")
        print("   1. Test RAG tool: 'zeig mir Stoffe'")
        print("   2. If embeddings need regeneration: run embedding generation script")
        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
