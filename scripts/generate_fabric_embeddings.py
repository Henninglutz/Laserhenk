"""
Generate Embeddings for all Fabrics in the Database

Dieses Skript:
1. Liest alle Stoffe aus der `fabrics` Tabelle
2. Erstellt 4 Content-Chunks pro Stoff:
   - Characteristics (Composition, Weight, Color, Pattern)
   - Visual Description (Visual attributes)
   - Usage Context (Category, Season, Occasion)
   - Technical Details (Care, Origin, Supplier)
3. Generiert Embeddings mit OpenAI text-embedding-3-small (384 dims)
4. Speichert in `fabric_embeddings` Tabelle

Usage:
    python scripts/generate_fabric_embeddings.py [--batch-size 50] [--dry-run]

Umgebungsvariablen:
    POSTGRES_CONNECTION_STRING: PostgreSQL Connection String
    OPENAI_API_KEY: OpenAI API Key
    EMBEDDING_DIMENSION: Target embedding dimensions (default: 384)
"""

import asyncio
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse
import json

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from dotenv import load_dotenv
import openai

# Load environment
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Support both DATABASE_URL and POSTGRES_CONNECTION_STRING
POSTGRES_CONNECTION_STRING = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
EMBEDDING_MODEL = "text-embedding-3-small"  # Supports flexible dimensions

# Validate environment
if not OPENAI_API_KEY:
    print("❌ Error: OPENAI_API_KEY not set in .env")
    sys.exit(1)

if not POSTGRES_CONNECTION_STRING:
    print("❌ Error: DATABASE_URL or POSTGRES_CONNECTION_STRING not set in .env")
    sys.exit(1)

# Configure OpenAI
openai.api_key = OPENAI_API_KEY


class FabricEmbeddingGenerator:
    """Generates and stores embeddings for fabric data."""

    def __init__(self, batch_size: int = 50, dry_run: bool = False):
        """
        Initialize the generator.

        Args:
            batch_size: Number of fabrics to process in one batch
            dry_run: If True, don't actually insert into database
        """
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.engine: Optional[AsyncEngine] = None
        self.stats = {
            "fabrics_processed": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "errors": 0,
            "total_tokens": 0,
        }

    async def initialize(self):
        """Initialize database connection."""
        # Convert to asyncpg URL if needed
        connection_string = POSTGRES_CONNECTION_STRING
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif connection_string.startswith("postgres://"):
            connection_string = connection_string.replace("postgres://", "postgresql+asyncpg://", 1)

        self.engine = create_async_engine(
            connection_string,
            echo=False,
            pool_size=10,
            max_overflow=20
        )
        print(f"✅ Database connection established")

    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    def create_fabric_chunks(self, fabric: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create content chunks for a fabric.

        Args:
            fabric: Fabric data from database

        Returns:
            List of chunks with content and metadata
        """
        chunks = []

        fabric_code = fabric["fabric_code"]
        name = fabric["name"] or f"Fabric {fabric_code}"

        # Chunk 1: Characteristics
        characteristics_parts = []
        if fabric["composition"]:
            characteristics_parts.append(fabric["composition"])
        if fabric["weight"]:
            characteristics_parts.append(f"{fabric['weight']}g/m²")
        if fabric["color"]:
            characteristics_parts.append(fabric["color"])
        if fabric["pattern"]:
            characteristics_parts.append(f"Muster: {fabric['pattern']}")

        if characteristics_parts:
            chunks.append({
                "chunk_id": f"{fabric_code}_characteristics",
                "chunk_type": "characteristics",
                "content": f"{name} - " + ", ".join(characteristics_parts),
                "metadata": {
                    "fabric_code": fabric_code,
                    "chunk_index": 0
                }
            })

        # Chunk 2: Visual Description
        visual_parts = []
        if fabric["color"]:
            visual_parts.append(f"Farbe: {fabric['color']}")
        if fabric["pattern"]:
            visual_parts.append(f"Muster: {fabric['pattern']}")

        # Extract visual hints from additional_metadata if available
        if fabric.get("additional_metadata"):
            try:
                metadata = json.loads(fabric["additional_metadata"]) if isinstance(fabric["additional_metadata"], str) else fabric["additional_metadata"]
                if "eigenschaften" in metadata:
                    visual_parts.append(f"Eigenschaften: {metadata['eigenschaften']}")
            except:
                pass

        if visual_parts:
            chunks.append({
                "chunk_id": f"{fabric_code}_visual",
                "chunk_type": "visual",
                "content": f"{name} - Visuell: " + ", ".join(visual_parts),
                "metadata": {
                    "fabric_code": fabric_code,
                    "chunk_index": 1
                }
            })

        # Chunk 3: Usage Context
        usage_parts = []
        if fabric["category"]:
            usage_parts.append(f"Kategorie: {fabric['category']}")
        if fabric["stock_status"]:
            usage_parts.append(f"Verfügbarkeit: {fabric['stock_status']}")

        # Infer season/occasion from category
        category_lower = (fabric["category"] or "").lower()
        if "business" in category_lower or "suit" in category_lower:
            usage_parts.append("Anlass: Business, Formell")
        elif "wedding" in category_lower or "hochzeit" in category_lower:
            usage_parts.append("Anlass: Hochzeit, Festlich")
        elif "casual" in category_lower:
            usage_parts.append("Anlass: Casual, Freizeit")

        if usage_parts:
            chunks.append({
                "chunk_id": f"{fabric_code}_usage",
                "chunk_type": "usage",
                "content": f"{name} - Verwendung: " + ", ".join(usage_parts),
                "metadata": {
                    "fabric_code": fabric_code,
                    "chunk_index": 2
                }
            })

        # Chunk 4: Technical Details
        technical_parts = []
        if fabric["supplier"]:
            technical_parts.append(f"Lieferant: {fabric['supplier']}")
        if fabric["origin"]:
            technical_parts.append(f"Herkunft: {fabric['origin']}")
        if fabric["care_instructions"]:
            technical_parts.append(f"Pflege: {fabric['care_instructions']}")

        if technical_parts:
            chunks.append({
                "chunk_id": f"{fabric_code}_technical",
                "chunk_type": "technical",
                "content": f"{name} - Technisch: " + ", ".join(technical_parts),
                "metadata": {
                    "fabric_code": fabric_code,
                    "chunk_index": 3
                }
            })

        return chunks

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts using OpenAI API.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        try:
            response = await asyncio.to_thread(
                openai.embeddings.create,
                input=texts,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSION
            )

            embeddings = [item.embedding for item in response.data]
            self.stats["total_tokens"] += response.usage.total_tokens

            return embeddings

        except Exception as e:
            print(f"❌ OpenAI API Error: {e}")
            raise

    async def fetch_fabrics(self, offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch a batch of fabrics from database.

        Args:
            offset: Starting offset
            limit: Number of fabrics to fetch

        Returns:
            List of fabric dictionaries
        """
        query = text("""
            SELECT
                id,
                fabric_code,
                name,
                supplier,
                composition,
                weight,
                color,
                pattern,
                category,
                stock_status,
                origin,
                care_instructions,
                additional_metadata
            FROM fabrics
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
        """)

        async with self.engine.begin() as conn:
            result = await conn.execute(query, {"limit": limit, "offset": offset})
            rows = result.fetchall()

        fabrics = []
        for row in rows:
            fabrics.append({
                "id": str(row.id),
                "fabric_code": row.fabric_code,
                "name": row.name,
                "supplier": row.supplier,
                "composition": row.composition,
                "weight": row.weight,
                "color": row.color,
                "pattern": row.pattern,
                "category": row.category,
                "stock_status": row.stock_status,
                "origin": row.origin,
                "care_instructions": row.care_instructions,
                "additional_metadata": row.additional_metadata
            })

        return fabrics

    async def insert_embeddings(self, embeddings_data: List[Dict[str, Any]]):
        """
        Insert embeddings into fabric_embeddings table.

        Args:
            embeddings_data: List of embedding records to insert
        """
        if self.dry_run:
            print(f"🏃 [DRY RUN] Would insert {len(embeddings_data)} embeddings")
            return

        # Use raw asyncpg connection for proper parameter binding
        query = """
            INSERT INTO fabric_embeddings (
                fabric_id,
                chunk_id,
                chunk_type,
                content,
                embedding,
                embedding_metadata
            ) VALUES (
                $1::uuid,
                $2,
                $3,
                $4,
                $5::vector,
                $6::jsonb
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                embedding_metadata = EXCLUDED.embedding_metadata,
                updated_at = NOW()
        """

        # Get the raw asyncpg connection
        async with self.engine.connect() as conn:
            raw_conn = await conn.get_raw_connection()
            async_conn = raw_conn.driver_connection

            for data in embeddings_data:
                await async_conn.execute(
                    query,
                    data["fabric_id"],
                    data["chunk_id"],
                    data["chunk_type"],
                    data["content"],
                    data["embedding"],
                    data["embedding_metadata"]
                )

            # Commit the transaction
            await conn.commit()

    async def process_batch(self, fabrics: List[Dict[str, Any]]):
        """
        Process a batch of fabrics.

        Args:
            fabrics: List of fabric dictionaries
        """
        if not fabrics:
            return

        print(f"📦 Processing batch of {len(fabrics)} fabrics...")

        # Create chunks for all fabrics
        all_chunks = []
        fabric_id_map = {}  # chunk_id -> fabric_id

        for fabric in fabrics:
            chunks = self.create_fabric_chunks(fabric)
            for chunk in chunks:
                all_chunks.append(chunk)
                fabric_id_map[chunk["chunk_id"]] = fabric["id"]

        if not all_chunks:
            print("⚠️  No valid chunks created for this batch")
            return

        self.stats["chunks_created"] += len(all_chunks)

        # Extract texts for embedding
        texts = [chunk["content"] for chunk in all_chunks]

        # Generate embeddings
        print(f"🔮 Generating {len(texts)} embeddings...")
        embeddings = await self.generate_embeddings(texts)
        self.stats["embeddings_generated"] += len(embeddings)

        # Prepare data for insertion
        embeddings_data = []
        for chunk, embedding in zip(all_chunks, embeddings):
            embeddings_data.append({
                "fabric_id": fabric_id_map[chunk["chunk_id"]],
                "chunk_id": chunk["chunk_id"],
                "chunk_type": chunk["chunk_type"],
                "content": chunk["content"],
                "embedding": str(embedding),  # Convert to string for PostgreSQL
                "embedding_metadata": json.dumps(chunk["metadata"])
            })

        # Insert into database
        await self.insert_embeddings(embeddings_data)

        self.stats["fabrics_processed"] += len(fabrics)

        print(f"✅ Batch complete: {len(fabrics)} fabrics, {len(embeddings)} embeddings")

    async def run(self):
        """Main execution loop."""
        print("=" * 70)
        print("🚀 FABRIC EMBEDDINGS GENERATOR")
        print("=" * 70)
        print(f"Model: {EMBEDDING_MODEL}")
        print(f"Dimensions: {EMBEDDING_DIMENSION}")
        print(f"Batch Size: {self.batch_size}")
        print(f"Dry Run: {self.dry_run}")
        print("=" * 70)

        await self.initialize()

        # Get total fabric count
        async with self.engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM fabrics"))
            total_fabrics = result.scalar()

        print(f"\n📊 Total fabrics in database: {total_fabrics}\n")

        if self.dry_run:
            print("🏃 DRY RUN MODE - No data will be inserted\n")

        # Process in batches
        offset = 0
        batch_num = 1

        try:
            while offset < total_fabrics:
                print(f"\n--- Batch {batch_num} (offset {offset}) ---")

                fabrics = await self.fetch_fabrics(offset, self.batch_size)
                if not fabrics:
                    break

                await self.process_batch(fabrics)

                offset += self.batch_size
                batch_num += 1

                # Progress
                progress = min(offset / total_fabrics * 100, 100)
                print(f"📈 Progress: {progress:.1f}% ({offset}/{total_fabrics})")

        except KeyboardInterrupt:
            print("\n⚠️  Process interrupted by user")
        except Exception as e:
            print(f"\n❌ Error during processing: {e}")
            self.stats["errors"] += 1
            raise
        finally:
            await self.close()

        # Final stats
        print("\n" + "=" * 70)
        print("✅ GENERATION COMPLETE")
        print("=" * 70)
        print(f"Fabrics Processed: {self.stats['fabrics_processed']}")
        print(f"Chunks Created: {self.stats['chunks_created']}")
        print(f"Embeddings Generated: {self.stats['embeddings_generated']}")
        print(f"Total Tokens Used: {self.stats['total_tokens']:,}")
        print(f"Estimated Cost: ${self.stats['total_tokens'] * 0.00000002:.4f}")
        if self.stats["errors"] > 0:
            print(f"⚠️  Errors: {self.stats['errors']}")
        print("=" * 70)


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings for all fabrics in the database"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of fabrics to process in each batch (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without inserting data (for testing)"
    )

    args = parser.parse_args()

    generator = FabricEmbeddingGenerator(
        batch_size=args.batch_size,
        dry_run=args.dry_run
    )

    await generator.run()


if __name__ == "__main__":
    asyncio.run(main())
