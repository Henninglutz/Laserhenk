"""RAG Tool - PostgreSQL Database Interface."""

import logging
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from models.fabric import FabricRecommendation, FabricSearchCriteria, FabricData
from models.tools import RAGQuery, RAGResult
from tools.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class RAGTool:
    """
    RAG Database Tool.

    Interface für PostgreSQL RAG Datenbank mit pgvector.
    Unterstützt semantic search mit OpenAI embeddings.
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize RAG Tool.

        Args:
            connection_string: PostgreSQL connection string (defaults to env var)
        """
        # Get connection string from env if not provided
        if connection_string is None:
            connection_string = os.getenv("DATABASE_URL") or os.getenv(
                "POSTGRES_CONNECTION_STRING"
            )

        if not connection_string:
            raise ValueError(
                "DATABASE_URL or POSTGRES_CONNECTION_STRING not set in environment"
            )

        # Convert to asyncpg format
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        elif connection_string.startswith("postgres://"):
            connection_string = connection_string.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )

        self.connection_string = connection_string
        self.engine: Optional[AsyncEngine] = None
        self.embedding_service = get_embedding_service()

        logger.info("[RAGTool] Initialized")

    def _get_engine(self) -> AsyncEngine:
        """Get or create database engine."""
        if self.engine is None:
            self.engine = create_async_engine(
                self.connection_string, echo=False, pool_size=5, max_overflow=10
            )
        return self.engine

    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None

    async def query(self, query_request: RAGQuery) -> RAGResult:
        """
        Query RAG database.

        Args:
            query_request: RAG query parameters

        Returns:
            RAG query results
        """
        # TODO: Implement actual RAG query logic
        # Placeholder für jetzt
        return RAGResult(
            results=[],
            metadata={"query": query_request.query},
        )

    async def retrieve_customer_context(self, customer_id: str) -> RAGResult:
        """
        Retrieve customer-specific context from RAG.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer context from database
        """
        # TODO: Implement customer context retrieval
        return RAGResult(results=[], metadata={"customer_id": customer_id})

    async def search_fabrics(
        self, criteria: FabricSearchCriteria
    ) -> list[FabricRecommendation]:
        """
        Search fabrics based on customer criteria.

        This is the main RAG query for fabric recommendations.
        Used by Design HENK to find matching fabrics based on HENK1 handoff.

        Args:
            criteria: Search criteria (colors, patterns, season, budget, etc.)

        Returns:
            List of fabric recommendations with similarity scores
        """
        logger.info(f"[RAGTool.search_fabrics] criteria={criteria}")

        try:
            # Build natural language query from criteria
            query_parts = []

            if criteria.colors:
                query_parts.append(f"Farben: {', '.join(criteria.colors)}")

            if criteria.patterns:
                query_parts.append(f"Muster: {', '.join(criteria.patterns)}")

            if criteria.season:
                query_parts.append(f"Saison: {criteria.season}")

            if criteria.occasion:
                query_parts.append(f"Anlass: {criteria.occasion}")

            if not query_parts:
                query_parts.append("Hochwertige Stoffe")

            query_text = " | ".join(query_parts)

            # Generate embedding for query
            query_embedding = await self.embedding_service.generate_embedding(
                query_text
            )
            embedding_str = str(query_embedding)

            # Build SQL with filters using positional parameters ($1, $2, ...)
            where_clauses = []
            params = [embedding_str]  # $1 = query_embedding
            param_count = 1

            # Budget filter
            if criteria.budget_min or criteria.budget_max:
                # Note: We'd need a price field in fabrics table
                # For now, skip this filter
                pass

            # Stock status filter
            if criteria.in_stock_only:
                where_clauses.append(
                    "f.stock_status IN ('in_stock', 'low_stock', 'on_order')"
                )

            where_sql = ""
            if where_clauses:
                where_sql = "AND " + " AND ".join(where_clauses)

            # Add limit as last parameter
            param_count += 1
            limit_param = f"${param_count}"
            params.append(criteria.limit)

            # Query fabric_embeddings with join to fabrics
            query_str = f"""
                SELECT
                    f.id,
                    f.fabric_code,
                    f.name,
                    f.composition,
                    f.weight,
                    f.color,
                    f.pattern,
                    f.category,
                    f.stock_status,
                    f.supplier,
                    f.origin,
                    f.care_instructions,
                    f.description,
                    f.additional_metadata,
                    fe.content,
                    1 - (fe.embedding <=> $1::vector) as similarity
                FROM fabric_embeddings fe
                JOIN fabrics f ON fe.fabric_id = f.id
                WHERE 1=1
                {where_sql}
                ORDER BY fe.embedding <=> $1::vector
                LIMIT {limit_param}
            """

            engine = self._get_engine()
            async with engine.connect() as conn:
                # Get raw asyncpg connection for vector operations
                raw_conn = await conn.get_raw_connection()
                async_conn = raw_conn.driver_connection

                results = await async_conn.fetch(query_str, *params)

            # Format results as FabricRecommendation
            recommendations = []
            for result in results:
                # Create FabricData
                fabric_data = FabricData(
                    fabric_code=result["fabric_code"],
                    name=result["name"],
                    composition=result["composition"],
                    weight=result["weight"],
                    color=result["color"],
                    pattern=result["pattern"],
                    category=result["category"],
                    stock_status=result["stock_status"],
                    supplier=result["supplier"] or "Formens",
                    origin=result["origin"],
                    care_instructions=result["care_instructions"],
                    description=result["description"],
                )

                # Determine match reasons
                match_reasons = []
                similarity = float(result["similarity"])

                if similarity > 0.85:
                    match_reasons.append("Sehr hohe Übereinstimmung mit Ihren Kriterien")
                elif similarity > 0.75:
                    match_reasons.append("Hohe Übereinstimmung mit Ihren Kriterien")
                else:
                    match_reasons.append("Gute Übereinstimmung mit Ihren Kriterien")

                if criteria.colors and result["color"]:
                    if any(
                        c.lower() in result["color"].lower() for c in criteria.colors
                    ):
                        match_reasons.append(f"Farbe passt: {result['color']}")

                if criteria.patterns and result["pattern"]:
                    if any(
                        p.lower() in result["pattern"].lower()
                        for p in criteria.patterns
                    ):
                        match_reasons.append(f"Muster passt: {result['pattern']}")

                # Create recommendation
                recommendation = FabricRecommendation(
                    fabric=fabric_data,
                    similarity_score=similarity,
                    match_reasons=match_reasons,
                )
                recommendations.append(recommendation)

            logger.info(
                f"[RAGTool.search_fabrics] Found {len(recommendations)} recommendations"
            )
            return recommendations

        except Exception as e:
            logger.error(f"[RAGTool.search_fabrics] Error: {e}", exc_info=True)
            # Return empty list on error
            return []

    async def get_fabric_by_code(self, fabric_code: str) -> Optional[dict]:
        """
        Get specific fabric by fabric code.

        Args:
            fabric_code: Fabric code (e.g., "PIANAM")

        Returns:
            Fabric data or None if not found
        """
        # TODO: Implement fabric lookup
        return None

    async def get_fabrics_for_occasion(
        self, occasion: str, season: Optional[str] = None
    ) -> list[dict]:
        """
        Get fabric recommendations for specific occasion.

        Args:
            occasion: Occasion type (e.g., "wedding", "business")
            season: Optional season filter

        Returns:
            List of suitable fabrics
        """
        # TODO: Implement occasion-based fabric query
        # This would query fabric_categories and join with fabrics
        return []

    async def search(
        self,
        query: str,
        fabric_type: Optional[str] = None,
        pattern: Optional[str] = None,
        limit: int = 10,
        category: Optional[str] = None,
    ) -> list[dict]:
        """
        Generic semantic search method for RAG queries.

        Uses pgvector cosine similarity to find relevant documents
        in the rag_docs table based on the query embedding.

        Args:
            query: Natural language search query
            fabric_type: Optional fabric type filter (e.g., "wool", "linen")
            pattern: Optional pattern filter (e.g., "pinstripe", "solid")
            limit: Maximum number of results to return
            category: Optional category filter (e.g., "fabrics", "shirts")

        Returns:
            List of search results with similarity scores
        """
        logger.info(
            f"[RAGTool.search] query='{query}', fabric_type={fabric_type}, "
            f"pattern={pattern}, category={category}"
        )

        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.generate_embedding(query)
            embedding_str = str(query_embedding)

            # Build query with optional filters using positional parameters ($1, $2, ...)
            where_clauses = []
            params = [embedding_str]  # $1 = query_embedding
            param_count = 1

            if category:
                param_count += 1
                where_clauses.append(f"meta_json->>'category' = ${param_count}")
                params.append(category)

            if fabric_type:
                param_count += 1
                where_clauses.append(f"content ILIKE ${param_count}")
                params.append(f"%{fabric_type}%")

            if pattern:
                param_count += 1
                where_clauses.append(f"content ILIKE ${param_count}")
                params.append(f"%{pattern}%")

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            # Add limit as last parameter
            param_count += 1
            limit_param = f"${param_count}"
            params.append(limit)

            # Execute similarity search
            query_str = f"""
                SELECT
                    doc_id,
                    meta_json->>'chunk_id' as chunk_id,
                    meta_json->>'category' as category,
                    content,
                    1 - (embedding <=> $1::vector) as similarity
                FROM rag_docs
                {where_sql}
                ORDER BY embedding <=> $1::vector
                LIMIT {limit_param}
            """

            engine = self._get_engine()
            async with engine.connect() as conn:
                # Get raw asyncpg connection for vector operations
                raw_conn = await conn.get_raw_connection()
                async_conn = raw_conn.driver_connection

                results = await async_conn.fetch(query_str, *params)

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "doc_id": str(result["doc_id"]),
                        "chunk_id": result["chunk_id"],
                        "category": result["category"],
                        "content": result["content"],
                        "similarity_score": float(result["similarity"]),
                    }
                )

            logger.info(f"[RAGTool.search] Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"[RAGTool.search] Error: {e}", exc_info=True)
            # Return empty results on error rather than crashing
            return []
