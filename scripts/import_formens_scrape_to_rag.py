"""Importiert die von ``scrape_formens_b2b.py`` erzeugten Stoffdaten in Postgres.

Funktionen:
- Upsert in die Tabelle ``fabrics`` (Code, Name, Zusammensetzung, Gewicht, Kategorie)
- Optional: Embeddings erzeugen und als RAG-Dokumente in ``rag_docs`` speichern

Benötigte Umgebungsvariablen:
- ``POSTGRES_CONNECTION_STRING`` oder ``DATABASE_URL`` (Postgres mit pgvector)
- ``OPENAI_API_KEY`` (nur für RAG-Import nötig)

Beispiel (nur Datenbank-Update, ohne RAG-Embeddings):
    python scripts/import_formens_scrape_to_rag.py \
        --input storage/fabrics/formens_fabrics.json \
        --no-rag

Beispiel (inkl. RAG-Embeddings):
    python scripts/import_formens_scrape_to_rag.py \
        --input storage/fabrics/formens_fabrics.json \
        --rag-category fabrics_formens \
        --batch-size 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import asyncpg
import openai
from dotenv import load_dotenv

# Lade .env falls vorhanden
load_dotenv()


@dataclass
class Fabric:
    """Repräsentiert einen Stoffeintrag aus dem Scraper."""

    code: str
    name: Optional[str]
    description: Optional[str]
    composition: Optional[str]
    weight: Optional[str]
    price_category: Optional[str]
    origin: Optional[str]
    image_url: Optional[str]
    image_path: Optional[str]
    url: str
    extra: Dict[str, Any]
    scraped_at: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Fabric":
        return Fabric(
            code=data.get("code") or data.get("fabric_code") or "",
            name=data.get("name"),
            description=data.get("description"),
            composition=data.get("composition"),
            weight=data.get("weight"),
            price_category=data.get("price_category"),
            origin=data.get("origin"),
            image_url=data.get("image_url"),
            image_path=data.get("image_path"),
            url=data.get("url", ""),
            extra=data.get("extra", {}),
            scraped_at=data.get("scraped_at") or datetime.utcnow().isoformat(),
        )

    def to_rag_payload(self, rag_category: str) -> Dict[str, Any]:
        """Erzeuge einen Text-Chunk für RAG."""

        parts: List[str] = [
            f"Formens Stoff {self.code}",
            f"Name: {self.name}" if self.name else None,
            f"Preis-Kategorie: {self.price_category}" if self.price_category else None,
            f"Zusammensetzung: {self.composition}" if self.composition else None,
            f"Gewicht: {self.weight}" if self.weight else None,
            f"Herkunft: {self.origin}" if self.origin else None,
            f"Beschreibung: {self.description}" if self.description else None,
        ]

        content = " | ".join(filter(None, parts))
        metadata = {
            "source": "formens_b2b_scraper",
            "fabric_code": self.code,
            "url": self.url,
            "image_url": self.image_url,
            "image_path": self.image_path,
            "price_category": self.price_category,
            "origin": self.origin,
            "scraped_at": self.scraped_at,
            "extra": self.extra,
        }

        return {
            "document_id": f"formens::{self.code}",
            "category": rag_category,
            "content": content,
            "metadata": metadata,
        }


class FormensImporter:
    """Importiert Scraper-Daten in die Postgres-Datenbank und optional in RAG."""

    def __init__(self, batch_size: int = 20, enable_rag: bool = True, rag_category: str = "fabrics_formens"):
        self.batch_size = batch_size
        self.enable_rag = enable_rag
        self.rag_category = rag_category
        self.db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
        self.conn: Optional[asyncpg.Connection] = None

        if not self.db_url:
            raise SystemExit("❌ DATABASE_URL oder POSTGRES_CONNECTION_STRING fehlt")

        if self.enable_rag:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise SystemExit("❌ OPENAI_API_KEY fehlt für RAG-Import")
            openai.api_key = api_key

    async def __aenter__(self) -> "FormensImporter":
        # asyncpg erwartet postgresql://
        url = self.db_url.replace("postgres://", "postgresql://", 1)
        self.conn = await asyncpg.connect(url)
        print("✅ Verbunden mit Postgres")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.conn:
            await self.conn.close()

    async def upsert_fabrics(self, fabrics: Iterable[Fabric]) -> None:
        assert self.conn
        inserted = updated = 0

        query = """
            INSERT INTO fabrics (
                fabric_code, name, composition, weight, supplier, category,
                description, additional_metadata, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW()
            )
            ON CONFLICT (fabric_code) DO UPDATE SET
                name = COALESCE(EXCLUDED.name, fabrics.name),
                composition = COALESCE(EXCLUDED.composition, fabrics.composition),
                weight = COALESCE(EXCLUDED.weight, fabrics.weight),
                supplier = COALESCE(EXCLUDED.supplier, fabrics.supplier),
                category = COALESCE(EXCLUDED.category, fabrics.category),
                description = COALESCE(EXCLUDED.description, fabrics.description),
                additional_metadata = fabrics.additional_metadata || EXCLUDED.additional_metadata,
                updated_at = NOW()
        """

        for fabric in fabrics:
            metadata = {
                "origin": fabric.origin,
                "price_category": fabric.price_category,
                "scraped_at": fabric.scraped_at,
                "image_url": fabric.image_url,
                "image_path": fabric.image_path,
                "extra": fabric.extra,
            }
            try:
                await self.conn.execute(
                    query,
                    fabric.code,
                    fabric.name,
                    fabric.composition,
                    fabric.weight,
                    "Formens B2B",
                    fabric.price_category,
                    fabric.description or fabric.name,
                    json.dumps(metadata),
                )
                # asyncpg execute returns status string: INSERT 0 1 or UPDATE 1 1
                # We can detect via string prefix
                # "INSERT 0 1" -> new row, "UPDATE 1" -> updated
                # For simplicity, increment both as successful writes
                inserted += 1
            except Exception as exc:  # noqa: BLE001
                print(f"❌ Fehler beim Upsert für {fabric.code}: {exc}")

        print(f"📥 Fabrics geschrieben: {inserted} Einträge (Insert/Update kombiniert)")

    async def generate_embedding(self, text: str) -> List[float]:
        response = await asyncio.to_thread(
            openai.embeddings.create,
            input=text,
            model="text-embedding-3-small",
        )
        return response.data[0].embedding

    async def import_rag(self, fabrics: Iterable[Fabric]) -> None:
        if not self.enable_rag:
            return
        assert self.conn

        payloads = [fab.to_rag_payload(self.rag_category) for fab in fabrics if fab.code]
        total = len(payloads)
        print(f"🔮 Erzeuge Embeddings für {total} Stoffe…")

        for i in range(0, total, self.batch_size):
            batch = payloads[i : i + self.batch_size]
            embeddings = []
            for item in batch:
                try:
                    embeddings.append(await self.generate_embedding(item["content"]))
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️  Embedding fehlgeschlagen für {item['document_id']}: {exc}")
                    embeddings.append(None)

            async with self.conn.transaction():
                for item, embedding in zip(batch, embeddings):
                    if embedding is None:
                        continue
                    try:
                        await self.conn.execute(
                            """
                            INSERT INTO rag_docs (
                                document_id, category, content, embedding,
                                metadata, created_at, updated_at
                            ) VALUES (
                                $1, $2, $3, $4::vector, $5::jsonb, NOW(), NOW()
                            )
                            ON CONFLICT (document_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                metadata = EXCLUDED.metadata,
                                updated_at = NOW()
                            """,
                            item["document_id"],
                            item["category"],
                            item["content"],
                            embedding,
                            json.dumps(item["metadata"]),
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"❌ RAG-Insert fehlgeschlagen für {item['document_id']}: {exc}")
                        continue

            print(
                f"✅ Batch {i//self.batch_size + 1}: {len(batch)} RAG-Dokumente geschrieben"
            )

    @staticmethod
    def load_fabrics(path: Path) -> List[Fabric]:
        if not path.exists():
            raise SystemExit(f"❌ Eingabedatei nicht gefunden: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        fabrics_raw = data.get("fabrics") if isinstance(data, dict) else data
        if fabrics_raw is None:
            raise SystemExit("❌ JSON hat kein 'fabrics'-Array")

        fabrics = [Fabric.from_dict(item) for item in fabrics_raw]
        print(f"📦 Geladen: {len(fabrics)} Stoffe aus {path}")
        return fabrics


async def main() -> None:
    parser = argparse.ArgumentParser(description="Formens-Scrape in Postgres/RAG importieren")
    parser.add_argument("--input", type=Path, required=True, help="Pfad zur formens_fabrics.json")
    parser.add_argument("--batch-size", type=int, default=20, help="Batchgröße für Embeddings")
    parser.add_argument("--no-rag", action="store_true", help="Nur fabrics-Tabelle updaten")
    parser.add_argument("--rag-category", default="fabrics_formens", help="Kategorie in rag_docs")

    args = parser.parse_args()

    fabrics = FormensImporter.load_fabrics(args.input)

    async with FormensImporter(
        batch_size=args.batch_size,
        enable_rag=not args.no_rag,
        rag_category=args.rag_category,
    ) as importer:
        await importer.upsert_fabrics(fabrics)
        await importer.import_rag(fabrics)

    print("\n🎯 Import abgeschlossen. RAG-Queries wie 'zeig mir Stoffe' sind jetzt möglich.")


if __name__ == "__main__":
    asyncio.run(main())
