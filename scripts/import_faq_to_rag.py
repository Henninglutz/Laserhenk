#!/usr/bin/env python3
"""Import FAQ und Unternehmensinformationen in RAG-Datenbank."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from tools.embedding_service import get_embedding_service
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()


async def import_faq_to_rag():
    """Importiere FAQ in RAG-Datenbank."""

    print("=" * 70)
    print("FAQ Import zu RAG-Datenbank")
    print("=" * 70)

    # Read FAQ file
    faq_file = Path(__file__).parent.parent / "knowledge" / "faq_unternehmen.md"

    if not faq_file.exists():
        print(f"❌ FAQ Datei nicht gefunden: {faq_file}")
        return

    print(f"\n📖 Lese FAQ von: {faq_file}")
    content = faq_file.read_text(encoding='utf-8')

    # Split into sections (by headers)
    sections = []
    current_section = []
    current_title = "Allgemein"

    for line in content.split('\n'):
        if line.startswith('# '):
            # New section
            if current_section:
                sections.append({
                    'title': current_title,
                    'content': '\n'.join(current_section)
                })
            current_title = line.replace('#', '').strip()
            current_section = []
        else:
            current_section.append(line)

    # Add last section
    if current_section:
        sections.append({
            'title': current_title,
            'content': '\n'.join(current_section)
        })

    print(f"✅ Gefunden: {len(sections)} Sektionen")

    # Database connection
    db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_CONNECTION_STRING')
    if not db_url:
        print("❌ DATABASE_URL nicht gesetzt!")
        return

    # Convert to asyncpg
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    elif db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql+asyncpg://', 1)

    engine = create_async_engine(db_url, echo=False)
    embedding_service = get_embedding_service()

    print("\n📊 Importiere Sektionen in RAG-Datenbank...")

    async with engine.begin() as conn:
        # Get raw connection for vector operations
        raw_conn = await conn.get_raw_connection()
        async_conn = raw_conn.driver_connection

        for idx, section in enumerate(sections, 1):
            title = section['title']
            content = section['content']

            # Skip empty sections
            if not content.strip():
                continue

            print(f"\n{idx}. {title[:50]}...")

            # Generate embedding
            full_text = f"{title}\n\n{content}"
            embedding = await embedding_service.generate_embedding(full_text)
            embedding_str = str(embedding)

            # Insert into rag_docs
            doc_id = f"faq_{idx}"

            query = """
                INSERT INTO rag_docs (doc_id, content, embedding, meta_json)
                VALUES ($1, $2, $3::vector, $4::jsonb)
                ON CONFLICT (doc_id) DO UPDATE
                SET content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    meta_json = EXCLUDED.meta_json
            """

            meta = {
                'category': 'faq',
                'title': title,
                'source': 'faq_unternehmen.md',
                'chunk_id': str(idx)
            }

            await async_conn.execute(
                query,
                doc_id,
                full_text,
                embedding_str,
                str(meta).replace("'", '"')  # Convert to JSON
            )

            print(f"   ✅ Importiert")

    await engine.dispose()

    print("\n" + "=" * 70)
    print(f"✅ Import abgeschlossen! {len(sections)} Sektionen importiert.")
    print("=" * 70)
    print("\nDie Agenten haben jetzt Zugriff auf:")
    print("  - Lieferzeiten & Prozess")
    print("  - Preise & Kalkulation")
    print("  - Maßnahme & Smartphone-Scan")
    print("  - Stoffe & Materialien")
    print("  - Umtausch & Änderungen")
    print("  - Zahlungsbedingungen")
    print("  - Versand & Lieferung")
    print("  - AGB & Rechtliches")
    print("  - FAQ")
    print("\nTest mit: python -c \"from tools.rag_tool import RAGTool; import asyncio; asyncio.run(RAGTool().search('Wie lange dauert die Lieferung?'))\"")


if __name__ == '__main__':
    asyncio.run(import_faq_to_rag())
