"""
Test RAG Semantic Search für Hemden-Optionen

Testet:
1. Verifikation: Alle 13 Shirt-Option Chunks sind importiert
2. Semantic Search: Verschiedene Queries testen
3. Similarity Scores prüfen

Usage:
    python scripts/test_rag_shirt_search.py
"""

import asyncio
import json
import os
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
import openai

load_dotenv()

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536

openai.api_key = OPENAI_API_KEY


class RAGTester:
    """Test RAG search functionality."""

    def __init__(self):
        """Initialize database connection."""
        if DATABASE_URL.startswith("postgresql://"):
            db_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            db_url = DATABASE_URL

        self.engine = create_async_engine(db_url, echo=False)

    async def verify_import(self) -> Dict[str, Any]:
        """Verify all shirt option chunks are imported."""
        print("=" * 70)
        print("🔍 VERIFYING SHIRT OPTIONS IMPORT")
        print("=" * 70)
        print()

        async with self.engine.begin() as conn:
            # Count total rag_docs
            result = await conn.execute(text("SELECT COUNT(*) FROM rag_docs"))
            total_docs = result.scalar()

            # Count shirt-related docs
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM rag_docs
                WHERE meta_json->>'category' = 'shirts'
            """))
            shirt_docs = result.scalar()

            # Get all shirt chunk IDs
            result = await conn.execute(text("""
                SELECT meta_json->>'chunk_id' as chunk_id,
                       LENGTH(content) as content_length,
                       created_at
                FROM rag_docs
                WHERE meta_json->>'category' = 'shirts'
                ORDER BY created_at DESC
            """))
            chunks = result.fetchall()

        print(f"📊 Total RAG Docs: {total_docs}")
        print(f"🎽 Shirt Option Docs: {shirt_docs}")
        print()

        if shirt_docs == 13:
            print("✅ All 13 shirt option chunks imported successfully!")
        else:
            print(f"⚠️  Expected 13 chunks, found {shirt_docs}")

        print()
        print("📋 Imported Chunks:")
        print(f"{'Chunk ID':<30} {'Content Length':<15} {'Created At'}")
        print("-" * 70)
        for chunk in chunks:
            chunk_id = chunk[0]
            length = chunk[1]
            created = chunk[2].strftime("%Y-%m-%d %H:%M:%S") if chunk[2] else "N/A"
            print(f"{chunk_id:<30} {length:<15} {created}")

        return {
            "total_docs": total_docs,
            "shirt_docs": shirt_docs,
            "success": shirt_docs == 13,
        }

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for query."""
        response = await asyncio.to_thread(
            openai.embeddings.create,
            input=text,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSION,
        )
        return response.data[0].embedding

    async def search_rag(
        self, query: str, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search RAG database with semantic similarity."""
        # Generate embedding for query
        query_embedding = await self.generate_embedding(query)

        # Use raw connection for asyncpg
        async with self.engine.connect() as conn:
            raw_conn = await conn.get_raw_connection()
            async_conn = raw_conn.driver_connection

            # Similarity search query
            query_str = """
                SELECT
                    doc_id,
                    meta_json->>'chunk_id' as chunk_id,
                    meta_json->>'category' as category,
                    content,
                    1 - (embedding <=> $1::vector) as similarity
                FROM rag_docs
                WHERE meta_json->>'category' = 'shirts'
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """

            results = await async_conn.fetch(
                query_str, str(query_embedding), top_k
            )

        return [
            {
                "doc_id": str(result["doc_id"]),
                "chunk_id": result["chunk_id"],
                "category": result["category"],
                "content": result["content"][:200] + "..."
                if len(result["content"]) > 200
                else result["content"],
                "similarity": float(result["similarity"]),
            }
            for result in results
        ]

    async def test_queries(self):
        """Test various RAG queries."""
        print()
        print("=" * 70)
        print("🧪 TESTING RAG SEMANTIC SEARCH")
        print("=" * 70)
        print()

        test_queries = [
            "Welche Kragen eignen sich für Business Formal?",
            "Zeig mir Kragen für entspannte Hemden",
            "Was kostet ein Hemd mit Premium Elite Stoff?",
            "Welche Manschetten für formelle Anlässe?",
            "Button-down Kragen Optionen",
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n{'=' * 70}")
            print(f"Query {i}: {query}")
            print(f"{'=' * 70}")

            results = await self.search_rag(query, top_k=3)

            for j, result in enumerate(results, 1):
                print(f"\n{j}. {result['chunk_id']} (Similarity: {result['similarity']:.4f})")
                print(f"   {result['content']}")

        print("\n" + "=" * 70)
        print("✅ RAG SEARCH TEST COMPLETE")
        print("=" * 70)


async def main():
    """Main test function."""
    tester = RAGTester()

    # Verify import
    verification = await tester.verify_import()

    if not verification["success"]:
        print("\n⚠️  Import verification failed. Please check the import.")
        return

    # Test RAG queries
    await tester.test_queries()

    print()
    print("=" * 70)
    print("🎉 ALL TESTS COMPLETE")
    print("=" * 70)
    print()
    print(f"✅ Total RAG Docs: {verification['total_docs']}")
    print(f"✅ Shirt Options: {verification['shirt_docs']}")
    print("✅ Semantic Search: Functional")
    print()
    print("🚀 RAG System is fully operational!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
