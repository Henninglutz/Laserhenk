"""
Update Fabric Metadata from Source

This script fills in missing fabric data (name, composition, color, pattern, weight)
from your original data source.

Usage:
    python scripts/update_fabric_metadata.py --source fabrics_data.csv
"""

import asyncio
import asyncpg
import argparse
import csv
import os
from pathlib import Path


async def check_fabric_completeness(conn):
    """Check how many fabrics are missing data."""
    query = """
        SELECT
            COUNT(*) as total,
            COUNT(name) as has_name,
            COUNT(composition) as has_composition,
            COUNT(color) as has_color,
            COUNT(pattern) as has_pattern,
            COUNT(weight) as has_weight
        FROM fabrics
    """
    result = await conn.fetchrow(query)

    print("=" * 80)
    print("FABRIC DATA COMPLETENESS REPORT")
    print("=" * 80)
    print(f"Total fabrics: {result['total']}")
    print(f"  - With name: {result['has_name']} ({result['has_name']/result['total']*100:.1f}%)")
    print(f"  - With composition: {result['has_composition']} ({result['has_composition']/result['total']*100:.1f}%)")
    print(f"  - With color: {result['has_color']} ({result['has_color']/result['total']*100:.1f}%)")
    print(f"  - With pattern: {result['has_pattern']} ({result['has_pattern']/result['total']*100:.1f}%)")
    print(f"  - With weight: {result['has_weight']} ({result['has_weight']/result['total']*100:.1f}%)")
    print()

    missing = result['total'] - result['has_name']
    if missing > 0:
        print(f"⚠️  {missing} fabrics are missing critical data!")
    else:
        print("✅ All fabrics have complete data!")
    print("=" * 80)
    print()


async def update_fabric_from_csv(conn, csv_path: Path):
    """
    Update fabric metadata from CSV file.

    Expected CSV format:
    fabric_code,name,composition,color,pattern,weight,supplier,origin,description
    70SH2109,Italienische Schurwolle Navy,100% Schurwolle,Navy,Uni,280,Vitale Barberis Canonico,Italien,Premium...
    """
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return

    print(f"📂 Reading fabric data from: {csv_path}")

    updated_count = 0
    skipped_count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            fabric_code = row.get('fabric_code')
            if not fabric_code:
                continue

            # Build update query dynamically based on available fields
            update_fields = []
            params = [fabric_code]
            param_idx = 2

            for field in ['name', 'composition', 'color', 'pattern', 'weight',
                         'supplier', 'origin', 'description', 'care_instructions']:
                if field in row and row[field]:
                    update_fields.append(f"{field} = ${param_idx}")
                    params.append(row[field])
                    param_idx += 1

            if not update_fields:
                skipped_count += 1
                continue

            query = f"""
                UPDATE fabrics
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE fabric_code = $1
            """

            try:
                result = await conn.execute(query, *params)
                if 'UPDATE 1' in result:
                    updated_count += 1
                    if updated_count % 100 == 0:
                        print(f"  ✓ Updated {updated_count} fabrics...")
                else:
                    skipped_count += 1
            except Exception as e:
                print(f"  ❌ Error updating {fabric_code}: {e}")
                skipped_count += 1

    print()
    print(f"✅ Updated {updated_count} fabrics")
    if skipped_count > 0:
        print(f"⚠️  Skipped {skipped_count} fabrics (no data or errors)")
    print()


async def generate_sample_csv(csv_path: Path):
    """Generate a sample CSV template."""
    print(f"📝 Generating sample CSV template: {csv_path}")

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'fabric_code', 'name', 'composition', 'color', 'pattern', 'weight',
            'supplier', 'origin', 'description', 'care_instructions'
        ])
        writer.writerow([
            '70SH2109',
            'Italienische Schurwolle Navy',
            '100% Schurwolle',
            'Navy',
            'Uni',
            '280',
            'Vitale Barberis Canonico',
            'Italien',
            'Premium Schurwolle für Anzüge, atmungsaktiv und knitterarm',
            'Chemische Reinigung'
        ])
        writer.writerow([
            '70SH2110',
            'Englisches Tweed Grau',
            '90% Schurwolle, 10% Kaschmir',
            'Grau',
            'Fischgrat',
            '320',
            'Holland & Sherry',
            'England',
            'Robustes Tweed-Gewebe für Winteranzüge',
            'Chemische Reinigung'
        ])

    print(f"✅ Sample CSV created: {csv_path}")
    print()
    print("Edit this file with your fabric data, then run:")
    print(f"  python scripts/update_fabric_metadata.py --source {csv_path}")
    print()


async def main():
    parser = argparse.ArgumentParser(description='Update fabric metadata in database')
    parser.add_argument('--source', type=str, help='Path to CSV file with fabric data')
    parser.add_argument('--check', action='store_true', help='Only check data completeness')
    parser.add_argument('--generate-template', type=str, help='Generate sample CSV template')

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

    # Remove +asyncpg if present
    db_url = db_url.replace('+asyncpg', '')

    try:
        conn = await asyncpg.connect(db_url)
        print(f"✅ Connected to database")
        print()

        if args.generate_template:
            template_path = Path(args.generate_template)
            await generate_sample_csv(template_path)
        elif args.check:
            await check_fabric_completeness(conn)
        elif args.source:
            await check_fabric_completeness(conn)
            print()
            await update_fabric_from_csv(conn, Path(args.source))
            print()
            await check_fabric_completeness(conn)
        else:
            # Default: just check
            await check_fabric_completeness(conn)
            print("💡 To update fabric data:")
            print("   1. Generate template: python scripts/update_fabric_metadata.py --generate-template fabrics_data.csv")
            print("   2. Fill in your fabric data in the CSV")
            print("   3. Update database: python scripts/update_fabric_metadata.py --source fabrics_data.csv")
            print()

        await conn.close()

    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())
