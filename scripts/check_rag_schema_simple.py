"""Simple script to check rag_docs table schema using psycopg2"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def check_schema():
    # Get connection string
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")

    if not db_url:
        print("❌ No DATABASE_URL or POSTGRES_CONNECTION_STRING found in .env")
        return

    # Convert postgresql+asyncpg:// to postgresql://
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    try:
        # Connect
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        print("✅ Connected to database")
        print("\n" + "="*70)
        print("rag_docs TABLE SCHEMA:")
        print("="*70)

        # Query schema
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'rag_docs'
            ORDER BY ordinal_position;
        """)

        rows = cur.fetchall()

        if not rows:
            print("❌ Table 'rag_docs' does not exist!")

            # List all tables
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cur.fetchall()
            print("\n📊 Available tables:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print(f"\n{'Column':<25} {'Type':<20} {'Nullable':<10} {'Default':<15}")
            print("-" * 70)
            for row in rows:
                col_name = row[0]
                col_type = row[1]
                nullable = row[2]
                default = row[3] if row[3] else ""
                print(f"{col_name:<25} {col_type:<20} {nullable:<10} {default:<15}")

        print("="*70)

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_schema()
