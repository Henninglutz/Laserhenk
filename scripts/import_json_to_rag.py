"""
Import JSON chunks to RAG database with embeddings

Dieses Script:
1. Liest JSON-Chunks aus extract_pdf_to_json.py
2. Generiert Embeddings mit OpenAI
3. Importiert in rag_docs Tabelle
4. Tracked Progress & Errors

Usage:
    python scripts/import_json_to_rag.py \
        --input drive_mirror/henk/shirts/hemden_chunks.json \
        --batch-size 20

Umgebungsvariablen:
    POSTGRES_CONNECTION_STRING: PostgreSQL Connection String
    OPENAI_API_KEY: OpenAI API Key
    EMBEDDING_DIMENSION: Target embedding dimensions (default: 1536)
"""

import asyncio
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from dotenv import load_dotenv
import openai

# Load environment
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POSTGRES_CONNECTION_STRING = os.getenv("DATABASE_URL") or os.getenv(
    "POSTGRES_CONNECTION_STRING"
)
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
EMBEDDING_MODEL = "text-embedding-3-small"

# Validate environment
if not OPENAI_API_KEY:
    print("❌ Error: OPENAI_API_KEY not set in .env")
    sys.exit(1)

if not POSTGRES_CONNECTION_STRING:
    print("❌ Error: DATABASE_URL or POSTGRES_CONNECTION_STRING not set in .env")
    sys.exit(1)

# Configure OpenAI
openai.api_key = OPENAI_API_KEY


class RAGImporter:
    """Imports JSON chunks to RAG database."""

    def __init__(self, batch_size: int = 20):
        """
        Initialize the importer.

        Args:
            batch_size: Number of chunks to process in one batch
        """
        self.batch_size = batch_size
        self.engine: AsyncEngine = None
        self.stats = {
            "chunks_processed": 0,
            "embeddings_generated": 0,
            "inserted": 0,
            "errors": 0,
        }

    async def initialize(self):
        """Initialize database connection."""
        connection_string = POSTGRES_CONNECTION_STRING
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        elif connection_string.startswith("postgres://"):
            connection_string = connection_string.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )

        self.engine = create_async_engine(
            connection_string, echo=False, pool_size=5, max_overflow=10
        )
        print("✅ Database connection established")

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        response = await asyncio.to_thread(
            openai.embeddings.create,
            input=text,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSION,
        )
        return response.data[0].embedding

    async def import_chunks(self, chunks: List[Dict[str, Any]], category: str):
        """
        Import chunks to rag_docs table.

        Args:
            chunks: List of chunk dicts
            category: Category name
        """
        print(f"\n🔮 Importiere {len(chunks)} Chunks...")

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            batch_num = (i // self.batch_size) + 1

            print(f"\n--- Batch {batch_num} (Chunks {i+1}-{i+len(batch)}) ---")
            print(f"📦 Processing {len(batch)} chunks...")

            # Generate embeddings for batch
            print(f"🔮 Generating {len(batch)} embeddings...")
            embeddings = []
            for chunk in batch:
                try:
                    embedding = await self.generate_embedding(chunk["content"])
                    embeddings.append(embedding)
                    self.stats["embeddings_generated"] += 1
                except Exception as e:
                    print(f"❌ Embedding Fehler: {e}")
                    embeddings.append(None)
                    self.stats["errors"] += 1

            # Insert into database
            print(f"💾 Inserting {len(batch)} chunks into rag_docs...")

            async with self.engine.begin() as conn:
                for chunk, embedding in zip(batch, embeddings):
                    if embedding is None:
                        continue

                    try:
                        # Insert into rag_docs
                        query = text(
                            """
                            INSERT INTO rag_docs (
                                document_id,
                                category,
                                content,
                                embedding,
                                metadata,
                                created_at
                            ) VALUES (
                                :document_id,
                                :category,
                                :content,
                                :embedding::vector,
                                :metadata::jsonb,
                                :created_at
                            )
                            ON CONFLICT (document_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata,
                                updated_at = NOW()
                        """
                        )

                        await conn.execute(
                            query,
                            {
                                "document_id": chunk["chunk_id"],
                                "category": category,
                                "content": chunk["content"],
                                "embedding": str(embedding),
                                "metadata": json.dumps(
                                    {
                                        "char_count": chunk.get("char_count", 0),
                                        "source": "pdf_import",
                                    }
                                ),
                                "created_at": datetime.now(),
                            },
                        )

                        self.stats["inserted"] += 1
                        self.stats["chunks_processed"] += 1

                    except Exception as e:
                        print(f"❌ Insert Fehler für {chunk['chunk_id']}: {e}")
                        self.stats["errors"] += 1

            print(
                f"✅ Batch complete: {len(batch)} chunks, {len([e for e in embeddings if e])} embeddings"
            )
            print(
                f"📈 Progress: {(i+len(batch))/len(chunks)*100:.1f}% ({i+len(batch)}/{len(chunks)})"
            )


async def main():
    """Main import function."""
    parser = argparse.ArgumentParser(
        description="Import JSON chunks to RAG database with embeddings"
    )
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument(
        "--batch-size", type=int, default=20, help="Chunks per batch"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("📥 JSON CHUNKS TO RAG DATABASE IMPORT")
    print("=" * 70)
    print(f"Input: {args.input}")
    print(f"Batch Size: {args.batch_size}")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Dimensions: {EMBEDDING_DIMENSION}")
    print()

    # Load JSON
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Fehler: JSON nicht gefunden: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data["chunks"]
    category = data["meta"]["category"]

    print(f"📊 Geladen: {len(chunks)} Chunks")
    print(f"   Category: {category}")
    print(f"   Total Chars: {data['meta']['total_chars']}")
    print()

    # Initialize importer
    importer = RAGImporter(batch_size=args.batch_size)
    await importer.initialize()

    # Import chunks
    try:
        await importer.import_chunks(chunks, category)
    finally:
        await importer.close()

    # Summary
    print("\n" + "=" * 70)
    print("✅ IMPORT COMPLETE")
    print("=" * 70)
    print(f"Chunks Processed: {importer.stats['chunks_processed']}")
    print(f"Embeddings Generated: {importer.stats['embeddings_generated']}")
    print(f"Inserted to DB: {importer.stats['inserted']}")
    print(f"Errors: {importer.stats['errors']}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
