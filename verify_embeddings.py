"""
Verifizierung der Embedding-Dimensionen in der Datenbank.
Korrigierte Version mit vector_dims() statt array_length().
"""

import asyncio
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

# Lade .env
load_dotenv()

# Erwartete Dimensionen aus .env
EXPECTED_DIMS = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# Tabellen mit Embedding-Spalten
TABLES_TO_CHECK = [
    ("embeddings", "embedding"),
    ("fabric_embeddings", "embedding"),
    ("rag_docs", "embedding"),
    ("henk_outfit_proposal", "embedding"),
    ("fabric_recommendations", "query_embedding"),
]


async def check_embedding_dimensions():
    """Prüft die Embedding-Dimensionen in allen relevanten Tabellen."""

    # Support both DATABASE_URL and POSTGRES_CONNECTION_STRING
    connection_string = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
    if not connection_string:
        print("❌ DATABASE_URL oder POSTGRES_CONNECTION_STRING nicht in .env gefunden")
        return

    # Async Engine für asyncpg
    engine = create_async_engine(connection_string, echo=False)

    print("=" * 70)
    print("🔬 EMBEDDING DIMENSIONEN ÜBERPRÜFUNG")
    print("=" * 70)
    print(f"\nErwartet (aus .env): {EXPECTED_DIMS} Dimensionen\n")

    results = {}

    async with engine.begin() as conn:
        for table_name, column_name in TABLES_TO_CHECK:
            try:
                # Korrigierte SQL-Abfrage mit vector_dims()
                query = text(f"""
                    SELECT vector_dims({column_name}) as dim
                    FROM {table_name}
                    WHERE {column_name} IS NOT NULL
                    LIMIT 1
                """)

                result = await conn.execute(query)
                row = result.fetchone()

                if row:
                    actual_dims = row[0]
                    status = "✅" if actual_dims == EXPECTED_DIMS else "⚠️"
                    results[f"{table_name}.{column_name}"] = actual_dims
                    print(f"{status} {table_name}.{column_name}: {actual_dims} Dimensionen")

                    if actual_dims != EXPECTED_DIMS:
                        print(f"   WARNUNG: Erwartet {EXPECTED_DIMS}, gefunden {actual_dims}")
                else:
                    print(f"ℹ️  {table_name}.{column_name}: Keine Daten vorhanden")
                    results[f"{table_name}.{column_name}"] = None

            except Exception as e:
                print(f"❌ {table_name}.{column_name}: Fehler - {e}")
                results[f"{table_name}.{column_name}"] = f"Error: {str(e)}"

    await engine.dispose()

    print("\n" + "=" * 70)
    print("📊 ZUSAMMENFASSUNG")
    print("=" * 70)

    has_data = [k for k, v in results.items() if v is not None and not isinstance(v, str)]
    no_data = [k for k, v in results.items() if v is None]
    errors = [k for k, v in results.items() if isinstance(v, str)]
    mismatches = [k for k, v in results.items() if isinstance(v, int) and v != EXPECTED_DIMS]

    if has_data:
        print(f"\n✅ Tabellen mit Embeddings: {len(has_data)}")
        for table in has_data:
            print(f"   - {table}: {results[table]} dims")

    if no_data:
        print(f"\nℹ️  Leere Tabellen: {len(no_data)}")
        for table in no_data:
            print(f"   - {table}")

    if errors:
        print(f"\n❌ Fehler: {len(errors)}")
        for table in errors:
            print(f"   - {table}")

    if mismatches:
        print(f"\n⚠️  Dimensionen-Mismatch: {len(mismatches)}")
        for table in mismatches:
            print(f"   - {table}: {results[table]} (erwartet: {EXPECTED_DIMS})")

    print("\n" + "=" * 70)
    print("💡 EMPFEHLUNGEN")
    print("=" * 70)

    if mismatches:
        print("\n⚠️  Embedding-Dimensionen stimmen nicht überein!")
        print("   → Embeddings müssen neu generiert werden")
        print("   → Oder EMBEDDING_DIMENSION in .env anpassen")
    elif has_data and not mismatches:
        print("\n✅ Alle Embedding-Dimensionen sind korrekt!")
        print("   → RAG Tool kann implementiert werden")
    elif no_data and not has_data:
        print("\n⚠️  Keine Embeddings gefunden!")
        print("   → Embeddings müssen erstellt werden")

    return results


if __name__ == "__main__":
    asyncio.run(check_embedding_dimensions())
