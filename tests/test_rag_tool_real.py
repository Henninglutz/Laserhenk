"""
Test RAGTool mit echter Datenbank-Anbindung

Testet:
1. RAGTool Initialisierung
2. EmbeddingService Integration
3. search() mit rag_docs Tabelle
4. search_fabrics() mit fabric_embeddings Tabelle
"""

import asyncio
import os
import sys
import pytest
import pytest_asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.rag_tool import RAGTool
from models.fabric import FabricSearchCriteria, Season


@pytest_asyncio.fixture
async def rag_tool():
    """Create RAGTool instance."""
    # Skip if no database connection available
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
    if not db_url:
        pytest.skip("No database connection available")

    tool = RAGTool()
    yield tool
    await tool.close()


@pytest.mark.asyncio
async def test_rag_tool_initialization(rag_tool):
    """Test that RAGTool initializes correctly."""
    assert rag_tool is not None
    assert rag_tool.connection_string is not None
    assert rag_tool.embedding_service is not None


@pytest.mark.asyncio
async def test_rag_search_basic(rag_tool):
    """Test basic RAG search functionality."""
    results = await rag_tool.search(
        query="Business formal suit fabrics",
        limit=5
    )

    # Results should be a list
    assert isinstance(results, list)

    # Each result should have expected fields
    for result in results:
        assert "doc_id" in result
        assert "content" in result
        assert "similarity_score" in result
        assert isinstance(result["similarity_score"], float)
        assert 0.0 <= result["similarity_score"] <= 1.0


@pytest.mark.asyncio
async def test_rag_search_with_category_filter(rag_tool):
    """Test RAG search with category filter."""
    results = await rag_tool.search(
        query="shirt collar options",
        category="shirts",
        limit=3
    )

    assert isinstance(results, list)

    # All results should be from shirts category
    for result in results:
        if result.get("category"):
            assert result["category"] == "shirts"


@pytest.mark.asyncio
async def test_search_fabrics(rag_tool):
    """Test fabric search with criteria."""
    criteria = FabricSearchCriteria(
        colors=["navy", "grau"],
        patterns=["nadelstreifen", "uni"],
        season=Season.FOUR_SEASON,
        occasion="business",
        in_stock_only=True,
        limit=5
    )

    recommendations = await rag_tool.search_fabrics(criteria)

    # Should return list of FabricRecommendation
    assert isinstance(recommendations, list)

    # Each recommendation should have expected structure
    for rec in recommendations:
        assert hasattr(rec, "fabric")
        assert hasattr(rec, "similarity_score")
        assert hasattr(rec, "match_reasons")

        # Fabric should have required fields
        fabric = rec.fabric
        assert fabric.fabric_code is not None
        assert isinstance(rec.similarity_score, float)
        assert 0.0 <= rec.similarity_score <= 1.0
        assert isinstance(rec.match_reasons, list)


@pytest.mark.asyncio
async def test_search_fabrics_minimal_criteria(rag_tool):
    """Test fabric search with minimal criteria."""
    criteria = FabricSearchCriteria(
        limit=3
    )

    recommendations = await rag_tool.search_fabrics(criteria)

    # Should return list even with minimal criteria
    assert isinstance(recommendations, list)


def test_rag_tool_handles_errors_gracefully():
    """Test that RAGTool handles errors gracefully."""
    # Try with invalid connection string
    # Set both env vars to None temporarily
    original_db_url = os.environ.get("DATABASE_URL")
    original_postgres = os.environ.get("POSTGRES_CONNECTION_STRING")

    try:
        # Remove env vars
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        if "POSTGRES_CONNECTION_STRING" in os.environ:
            del os.environ["POSTGRES_CONNECTION_STRING"]

        with pytest.raises(ValueError):
            tool = RAGTool(connection_string=None)
    finally:
        # Restore env vars
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        if original_postgres:
            os.environ["POSTGRES_CONNECTION_STRING"] = original_postgres


def test_embedding_service_singleton():
    """Test that embedding service is properly initialized."""
    from tools.embedding_service import get_embedding_service

    # Get service twice to test singleton
    service1 = get_embedding_service()
    service2 = get_embedding_service()

    assert service1 is service2  # Should be same instance
    assert service1.dimensions == int(os.getenv("EMBEDDING_DIMENSION", "1536"))


if __name__ == "__main__":
    # Run tests manually for debugging
    async def run_tests():
        print("=" * 80)
        print("TESTING RAG TOOL WITH REAL DATABASE")
        print("=" * 80)
        print()

        # Check environment
        db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
        api_key = os.getenv("OPENAI_API_KEY")

        if not db_url:
            print("❌ DATABASE_URL or POSTGRES_CONNECTION_STRING not set")
            return

        if not api_key:
            print("❌ OPENAI_API_KEY not set")
            return

        print(f"✓ Database URL configured")
        print(f"✓ OpenAI API Key configured")
        print()

        # Create RAGTool
        print("Creating RAGTool...")
        tool = RAGTool()
        print("✓ RAGTool initialized")
        print()

        # Test 1: Basic search
        print("Test 1: Basic RAG search")
        print("-" * 40)
        results = await tool.search("Business anzug stoffe", limit=3)
        print(f"Found {len(results)} results")
        for i, result in enumerate(results, 1):
            print(f"  {i}. Similarity: {result['similarity_score']:.3f}")
            print(f"     Content: {result['content'][:100]}...")
        print()

        # Test 2: Fabric search
        print("Test 2: Fabric search with criteria")
        print("-" * 40)
        criteria = FabricSearchCriteria(
            colors=["navy"],
            patterns=["nadelstreifen"],
            season=Season.FOUR_SEASON,
            limit=3
        )
        recommendations = await tool.search_fabrics(criteria)
        print(f"Found {len(recommendations)} recommendations")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec.fabric.name or rec.fabric.fabric_code}")
            print(f"     Similarity: {rec.similarity_score:.3f}")
            print(f"     Reasons: {', '.join(rec.match_reasons[:2])}")
        print()

        await tool.close()

        print("=" * 80)
        print("✓ ALL TESTS COMPLETED")
        print("=" * 80)

    asyncio.run(run_tests())
