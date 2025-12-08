"""
Database Inspector Script

Prüft PostgreSQL-Verbindung, Tabellen und Vector-Extension.
"""

import asyncio
import sys
from sqlalchemy import text
from database import Database


async def inspect_database():
    """Inspect PostgreSQL database setup"""
    print("=" * 60)
    print("LASERHENK Database Inspector")
    print("=" * 60)

    try:
        db = Database()
        print(f"\n✅ Database URL: {db._mask_url(db.database_url)}")
        print(f"✅ Embedding Dimension: {db.embedding_dim}")

    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        sys.exit(1)

    async with db.session() as session:
        print("\n" + "=" * 60)
        print("1. PostgreSQL Version")
        print("=" * 60)
        try:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ {version}")
        except Exception as e:
            print(f"❌ Error: {e}")

        print("\n" + "=" * 60)
        print("2. pgvector Extension")
        print("=" * 60)
        try:
            result = await session.execute(
                text("SELECT * FROM pg_extension WHERE extname = 'vector'")
            )
            ext = result.fetchone()
            if ext:
                print(f"✅ pgvector extension installed (version: {ext[1]})")
            else:
                print("❌ pgvector extension NOT installed")
                print("   Install: CREATE EXTENSION vector;")
        except Exception as e:
            print(f"❌ Error: {e}")

        print("\n" + "=" * 60)
        print("3. Database Tables")
        print("=" * 60)
        try:
            result = await session.execute(
                text(
                    """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """
                )
            )
            tables = result.fetchall()
            if tables:
                print(f"✅ Found {len(tables)} tables:")
                for table in tables:
                    print(f"   - {table[0]}")
            else:
                print("⚠️  No tables found")
        except Exception as e:
            print(f"❌ Error: {e}")

        print("\n" + "=" * 60)
        print("4. Vector Columns (pgvector)")
        print("=" * 60)
        try:
            result = await session.execute(
                text(
                    """
                SELECT
                    c.table_name,
                    c.column_name,
                    c.udt_name
                FROM information_schema.columns c
                WHERE c.table_schema = 'public'
                  AND c.udt_name = 'vector'
                ORDER BY c.table_name, c.column_name
            """
                )
            )
            vectors = result.fetchall()
            if vectors:
                print(f"✅ Found {len(vectors)} vector column(s):")
                for vec in vectors:
                    print(f"   - {vec[0]}.{vec[1]} ({vec[2]})")
            else:
                print("⚠️  No vector columns found")
        except Exception as e:
            print(f"❌ Error: {e}")

        print("\n" + "=" * 60)
        print("5. Sample Data Check")
        print("=" * 60)

        # Check common table names
        for table_name in ["fabrics", "fabric_embeddings", "customers"]:
            try:
                result = await session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                count = result.scalar()
                print(f"✅ {table_name}: {count} rows")
            except Exception:
                print(f"⚠️  {table_name}: table not found")

    await db.close()

    print("\n" + "=" * 60)
    print("Inspection Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(inspect_database())
