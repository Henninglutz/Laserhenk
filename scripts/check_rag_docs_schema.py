"""Quick script to check rag_docs table schema"""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()

async def check_schema():
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        # Get table schema
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'rag_docs'
            ORDER BY ordinal_position;
        """))

        print("rag_docs table schema:")
        print("-" * 60)
        for row in result:
            print(f"{row[0]:<20} {row[1]:<20} nullable: {row[2]}")

    await engine.dispose()

asyncio.run(check_schema())
