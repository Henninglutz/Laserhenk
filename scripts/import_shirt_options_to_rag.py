"""
Import Shirt Options to RAG Database

Dieses Script:
1. Liest shirt_options_detailed.json
2. Erstellt strukturierte RAG-Chunks pro Kategorie
3. Generiert Embeddings
4. Importiert in rag_docs Tabelle

Usage:
    python scripts/import_shirt_options_to_rag.py
"""

import asyncio
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


class ShirtOptionsImporter:
    """Imports shirt options to RAG database."""

    def __init__(self):
        """Initialize the importer."""
        self.engine: AsyncEngine = None
        self.stats = {
            "chunks_created": 0,
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
        """Generate embedding for text."""
        response = await asyncio.to_thread(
            openai.embeddings.create,
            input=text,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSION,
        )
        return response.data[0].embedding

    def create_chunks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create RAG chunks from shirt options data."""
        chunks = []

        # Pricing chunk
        pricing = data.get("pricing", {})
        pricing_content = f"""HEMDEN PREISE (inkl. MwSt.):

PREMIUM ELITE & PARADISE Stoffe: €{pricing['premium_elite']['price_eur']}
- Fabrics: {', '.join(pricing['premium_elite']['fabrics'])}

STANDARD Stoffe: €{pricing['standard']['price_eur']}
- Alle anderen Hemdenstoffe
"""
        chunks.append(
            {
                "chunk_id": "shirts_pricing",
                "category": "shirts",
                "content": pricing_content,
                "metadata": {"section": "pricing"},
            }
        )

        # Collar models chunk (standard)
        collars_standard = data["sections"]["collar_models"]["standard"]
        collar_lines = ["HEMDEN KRAGENFORMEN - Standard:"]
        for collar in collars_standard:
            # Build description based on available fields
            desc_parts = [f"{collar['name']} ({collar['code']}): {collar['type']}"]

            if "collar_stand_mm" in collar:
                desc_parts.append(f"Stand {collar['collar_stand_mm']}mm")
            if "collar_point_mm" in collar:
                desc_parts.append(f"Spitze {collar['collar_point_mm']}mm")

            collar_lines.append("\n" + ", ".join(desc_parts))

            if "notes" in collar:
                collar_lines.append(f"  Hinweis: {collar['notes']}")

        chunks.append(
            {
                "chunk_id": "shirts_collars_standard",
                "category": "shirts",
                "content": "\n".join(collar_lines),
                "metadata": {"section": "collars", "type": "standard"},
            }
        )

        # Collar models chunk (special)
        collars_special = data["sections"]["collar_models"]["special"]
        special_lines = ["HEMDEN KRAGENFORMEN - Spezial:"]
        for collar in collars_special:
            desc = f"\n{collar['name']} ({collar['code']})"
            if "collar_stand_mm" in collar:
                desc += f": Stand {collar['collar_stand_mm']}mm"
            special_lines.append(desc)

            if "notes" in collar:
                special_lines.append(f"  Hinweis: {collar['notes']}")

        chunks.append(
            {
                "chunk_id": "shirts_collars_special",
                "category": "shirts",
                "content": "\n".join(special_lines),
                "metadata": {"section": "collars", "type": "special"},
            }
        )

        # Collar construction
        construction = data["sections"]["collar_models"]["construction"]

        # Stiffness
        stiff_lines = ["KRAGEN VERSTEIFUNG:"]
        for option in construction["stiffness"]:
            stiff_lines.append(
                f"\n{option['name']} ({option['code']}): {option['description']}"
            )

        chunks.append(
            {
                "chunk_id": "shirts_collar_stiffness",
                "category": "shirts",
                "content": "\n".join(stiff_lines),
                "metadata": {"section": "collar_construction", "type": "stiffness"},
            }
        )

        # Cuffs standard
        cuffs_standard = data["sections"]["cuffs"]["standard"]
        cuff_lines = ["MANSCHETTEN - Standard:"]
        for cuff in cuffs_standard:
            desc = f"\n{cuff['name']} ({cuff['code']})"
            if "height_mm" in cuff:
                desc += f": Höhe {cuff['height_mm']}mm"
            cuff_lines.append(desc)

        chunks.append(
            {
                "chunk_id": "shirts_cuffs_standard",
                "category": "shirts",
                "content": "\n".join(cuff_lines),
                "metadata": {"section": "cuffs", "type": "standard"},
            }
        )

        # French cuffs
        cuffs_french = data["sections"]["cuffs"]["french_cuffs"]
        french_lines = ["MANSCHETTEN - Französisch (Umschlag):"]
        for cuff in cuffs_french:
            desc = f"\n{cuff['name']} ({cuff['code']})"
            if "height_mm" in cuff:
                desc += f": Höhe {cuff['height_mm']}mm"
            french_lines.append(desc)

        chunks.append(
            {
                "chunk_id": "shirts_cuffs_french",
                "category": "shirts",
                "content": "\n".join(french_lines),
                "metadata": {"section": "cuffs", "type": "french"},
            }
        )

        # Fronts - classic
        fronts_classic = data["sections"]["fronts"]["classic"]
        front_lines = ["HEMDEN VORDERTEIL - Klassisch:"]
        for front in fronts_classic:
            front_lines.append(f"\n{front['name']} ({front['code']})")

        chunks.append(
            {
                "chunk_id": "shirts_fronts_classic",
                "category": "shirts",
                "content": "\n".join(front_lines),
                "metadata": {"section": "fronts", "type": "classic"},
            }
        )

        # Fronts - ceremony
        fronts_ceremony = data["sections"]["fronts"]["ceremony"]
        ceremony_lines = ["HEMDEN VORDERTEIL - Zeremonie/Smoking:"]
        for front in fronts_ceremony:
            ceremony_lines.append(f"\n{front['name']} ({front['code']})")

        chunks.append(
            {
                "chunk_id": "shirts_fronts_ceremony",
                "category": "shirts",
                "content": "\n".join(ceremony_lines),
                "metadata": {"section": "fronts", "type": "ceremony"},
            }
        )

        # Backs
        backs = data["sections"]["backs"]
        back_lines = ["HEMDEN RÜCKENTEIL:"]
        for back in backs:
            back_lines.append(f"\n{back['name']} ({back['code']})")
            if "notes" in back:
                back_lines.append(f"  Hinweis: {back['notes']}")

        chunks.append(
            {
                "chunk_id": "shirts_backs",
                "category": "shirts",
                "content": "\n".join(back_lines),
                "metadata": {"section": "backs"},
            }
        )

        # Bottoms
        bottoms = data["sections"]["bottoms"]
        bottom_lines = ["HEMDEN SAUM (Bottom):"]
        for bottom in bottoms:
            bottom_lines.append(
                f"\n{bottom['name']} ({bottom['code']}): {bottom['front_vs_back']}"
            )

        chunks.append(
            {
                "chunk_id": "shirts_bottoms",
                "category": "shirts",
                "content": "\n".join(bottom_lines),
                "metadata": {"section": "bottoms"},
            }
        )

        # Pockets
        pockets_layout = data["sections"]["pockets"]["layout"]
        pockets_shapes = data["sections"]["pockets"]["shapes"]

        pocket_lines = ["HEMDEN TASCHEN:"]
        pocket_lines.append("\nLayout:")
        for layout in pockets_layout:
            pocket_lines.append(f"  {layout['name']} ({layout['code']})")

        pocket_lines.append("\nFormen:")
        for shape in pockets_shapes:
            pocket_lines.append(f"  {shape['name']} ({shape['code']})")

        chunks.append(
            {
                "chunk_id": "shirts_pockets",
                "category": "shirts",
                "content": "\n".join(pocket_lines),
                "metadata": {"section": "pockets"},
            }
        )

        # Monogram
        monogram = data["sections"]["monogram"]
        mono_lines = ["MONOGRAMM OPTIONEN:"]

        mono_lines.append("\nPositionen:")
        for pos in monogram["positions"][:5]:  # First 5
            mono_lines.append(f"  {pos['name']} ({pos['code']})")
        mono_lines.append(f"  ... und {len(monogram['positions']) - 5} weitere")

        mono_lines.append("\nSchriftarten:")
        for font in monogram["font_types"]:
            mono_lines.append(f"  {font['name']} ({font['code']})")

        mono_lines.append(f"\nGarnfarben: {len(monogram['thread_colors'])} Farben verfügbar")

        chunks.append(
            {
                "chunk_id": "shirts_monogram",
                "category": "shirts",
                "content": "\n".join(mono_lines),
                "metadata": {"section": "monogram"},
            }
        )

        # Fabric contrast
        fabric_contrast = data["sections"]["fabric_contrast"]
        contrast_lines = ["STOFF KONTRASTE:"]
        for contrast in fabric_contrast:
            contrast_lines.append(f"\n{contrast['name']} ({contrast['code']})")

        chunks.append(
            {
                "chunk_id": "shirts_fabric_contrast",
                "category": "shirts",
                "content": "\n".join(contrast_lines),
                "metadata": {"section": "fabric_contrast"},
            }
        )

        print(f"✅ Created {len(chunks)} chunks")
        self.stats["chunks_created"] = len(chunks)
        return chunks

    async def import_chunks(self, chunks: List[Dict[str, Any]]):
        """Import chunks to rag_docs table."""
        print(f"\n🔮 Importiere {len(chunks)} Chunks...")

        for i, chunk in enumerate(chunks, 1):
            print(f"📦 Processing chunk {i}/{len(chunks)}: {chunk['chunk_id']}")

            try:
                # Generate embedding
                embedding = await self.generate_embedding(chunk["content"])
                self.stats["embeddings_generated"] += 1

                # Insert into database
                async with self.engine.begin() as conn:
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
                            "category": chunk["category"],
                            "content": chunk["content"],
                            "embedding": str(embedding),
                            "metadata": json.dumps(chunk["metadata"]),
                            "created_at": datetime.now(),
                        },
                    )

                self.stats["inserted"] += 1
                print(f"✅ Inserted: {chunk['chunk_id']}")

            except Exception as e:
                print(f"❌ Error for {chunk['chunk_id']}: {e}")
                self.stats["errors"] += 1


async def main():
    """Main import function."""
    print("=" * 70)
    print("📥 SHIRT OPTIONS TO RAG DATABASE IMPORT")
    print("=" * 70)
    print()

    # Load JSON
    json_path = Path("drive_mirror/henk/shirts/shirt_options_detailed.json")
    if not json_path.exists():
        print(f"❌ Fehler: JSON nicht gefunden: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📊 Geladen: shirt_options_detailed.json")
    print(f"   Version: {data['version']}")
    print(f"   Updated: {data['updated']}")
    print()

    # Initialize importer
    importer = ShirtOptionsImporter()
    await importer.initialize()

    # Create chunks
    chunks = importer.create_chunks(data)

    # Import chunks
    try:
        await importer.import_chunks(chunks)
    finally:
        await importer.close()

    # Summary
    print("\n" + "=" * 70)
    print("✅ IMPORT COMPLETE")
    print("=" * 70)
    print(f"Chunks Created: {importer.stats['chunks_created']}")
    print(f"Embeddings Generated: {importer.stats['embeddings_generated']}")
    print(f"Inserted to DB: {importer.stats['inserted']}")
    print(f"Errors: {importer.stats['errors']}")
    print("=" * 70)
    print()
    print("🎯 Hemden-Optionen sind jetzt in der RAG-Datenbank!")
    print("   Category: 'shirts'")
    print("   Chunks: Kragen, Manschetten, Fronts, Backs, Preise, etc.")


if __name__ == "__main__":
    asyncio.run(main())
