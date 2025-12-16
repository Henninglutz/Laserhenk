"""RAG Tool - PostgreSQL Database Interface."""

import logging
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from models.fabric import FabricRecommendation, FabricSearchCriteria, FabricData
from models.tools import RAGQuery, RAGResult
from tools.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


# Pre-index local fabric images for quick lookup
_FABRIC_IMAGE_DIR = Path(__file__).resolve().parent.parent / "storage" / "fabrics" / "images"
_FABRIC_IMAGE_INDEX = {}
if _FABRIC_IMAGE_DIR.exists():  # pragma: no branch - defensive guard
    for file in _FABRIC_IMAGE_DIR.iterdir():
        if not file.is_file():
            continue
        stem = file.stem.upper().replace(" ", "")
        # store both raw stem and a version with separators normalized for fuzzy matching
        _FABRIC_IMAGE_INDEX[stem] = file.name
        _FABRIC_IMAGE_INDEX[stem.replace(".", "_")] = file.name


def _find_local_image(fabric_code: Optional[str]) -> list[str]:
    """Return accessible local image paths for a fabric code if available."""

    if not fabric_code:
        return []

    variants = {
        fabric_code,
        fabric_code.replace("/", "_"),
        fabric_code.replace("/", "_").replace(".", "_"),
        fabric_code.replace(" ", ""),
        fabric_code.replace(".", "_"),
    }

    for variant in variants:
        key = variant.upper()
        if key in _FABRIC_IMAGE_INDEX:
            filename = _FABRIC_IMAGE_INDEX[key]
            return [f"/fabrics/images/{filename}"]

        normalized = key.replace(".", "_")
        if normalized in _FABRIC_IMAGE_INDEX:
            filename = _FABRIC_IMAGE_INDEX[normalized]
            return [f"/fabrics/images/{filename}"]

    return []


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
        Query RAG database with semantic search.

        Args:
            query_request: RAG query parameters

        Returns:
            RAG query results
        """
        logger.info(f"[RAGTool.query] query='{query_request.query}'")

        # Use generic search method
        results = await self.search(
            query=query_request.query,
            limit=query_request.limit,
            category=query_request.category,
        )

        return RAGResult(
            results=results,
            metadata={
                "query": query_request.query,
                "count": len(results),
            },
        )

    async def retrieve_customer_context(self, customer_id: str) -> RAGResult:
        """
        Retrieve customer-specific context from RAG.

        Args:
            customer_id: Customer identifier

        Returns:
            Customer context from database
        """
        logger.info(f"[RAGTool.retrieve_customer_context] customer_id={customer_id}")

        # Search for customer-specific documents
        query = f"Customer preferences and history for {customer_id}"
        results = await self.search(
            query=query,
            category="customer",
            limit=5,
        )

        return RAGResult(
            results=results,
            metadata={
                "customer_id": customer_id,
                "count": len(results),
            },
        )

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

            if criteria.preferred_materials:
                query_parts.append(
                    f"Materialien: {', '.join(criteria.preferred_materials)}"
                )

            if criteria.weight_max:
                query_parts.append(f"Gewicht <= {criteria.weight_max}g/m²")

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

            # Weight preference (e.g., leichte Stoffe < 260g)
            if criteria.weight_max:
                param_count += 1
                where_clauses.append(f"f.weight IS NULL OR f.weight <= ${param_count}")
                params.append(criteria.weight_max)

            # Material hints (linen/cotton) to boost lightweight feel
            if criteria.preferred_materials:
                material_clauses = []
                for material in criteria.preferred_materials:
                    param_count += 1
                    material_clauses.append(f"f.composition ILIKE ${param_count}")
                    params.append(f"%{material}%")
                if material_clauses:
                    where_clauses.append("(" + " OR ".join(material_clauses) + ")")

            # IMPORTANT: Exclude shirts - only return suit fabrics
            # Shirts have fabric_code starting with 'SH' or category containing 'shirt'
            where_clauses.append(
                "(f.fabric_code NOT LIKE 'SH%' AND f.fabric_code NOT LIKE '%SH%')"
            )
            where_clauses.append(
                "(f.category IS NULL OR (f.category NOT ILIKE '%shirt%' AND f.category NOT ILIKE '%hemd%'))"
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
                # Extract image URLs from additional_metadata
                metadata = result.get("additional_metadata") or {}
                image_url = metadata.get("image_url")
                image_path = metadata.get("image_path")

                # Build image lists
                # Prefer database image_url/path; fallback to local storage lookup
                local_image_paths = [image_path] if image_path else []
                if not local_image_paths:
                    local_image_paths = _find_local_image(result["fabric_code"])

                image_urls = [image_url] if image_url else []
                if not image_urls and local_image_paths:
                    image_urls = local_image_paths

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
                    image_urls=image_urls,
                    local_image_paths=local_image_paths,
                    additional_metadata=metadata,
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

                if criteria.weight_max and result["weight"]:
                    try:
                        weight_val = int(result["weight"])
                        if weight_val <= criteria.weight_max:
                            match_reasons.append(
                                f"Leichtes Gewicht: {weight_val}g/m²"
                            )
                    except (TypeError, ValueError):
                        pass

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
