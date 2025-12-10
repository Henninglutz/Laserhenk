"""
Embedding Service - OpenAI Embeddings Generation

Zentrale Klasse für Embedding-Generierung mit OpenAI API.
Verwendet text-embedding-3-small mit konfigurierbaren Dimensionen.
"""

import asyncio
import os
from typing import List, Optional
import logging

import openai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI API.

    Features:
    - Batch embedding generation
    - Configurable dimensions (default: 1536)
    - Automatic retry logic
    - Token usage tracking
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        """
        Initialize Embedding Service.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model name
            dimensions: Vector dimensions (must match database schema!)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")

        self.model = model
        self.dimensions = dimensions

        # Configure OpenAI client
        openai.api_key = self.api_key

        # Stats tracking
        self.total_tokens = 0
        self.total_requests = 0

        logger.info(
            f"[EmbeddingService] Initialized: model={model}, dimensions={dimensions}"
        )

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            Exception: If API call fails
        """
        return (await self.generate_embeddings([text]))[0]

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a batch.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If API call fails
        """
        if not texts:
            return []

        try:
            # Call OpenAI API in thread (openai lib uses sync calls)
            response = await asyncio.to_thread(
                openai.embeddings.create,
                input=texts,
                model=self.model,
                dimensions=self.dimensions,
            )

            # Extract embeddings
            embeddings = [item.embedding for item in response.data]

            # Update stats
            self.total_tokens += response.usage.total_tokens
            self.total_requests += 1

            logger.debug(
                f"[EmbeddingService] Generated {len(embeddings)} embeddings "
                f"({response.usage.total_tokens} tokens)"
            )

            return embeddings

        except Exception as e:
            logger.error(f"[EmbeddingService] API Error: {e}")
            raise

    def get_stats(self) -> dict:
        """
        Get usage statistics.

        Returns:
            Dict with total_tokens and total_requests
        """
        return {
            "total_tokens": self.total_tokens,
            "total_requests": self.total_requests,
            "estimated_cost_usd": self.total_tokens * 0.00000002,  # $0.02/1M tokens
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self.total_tokens = 0
        self.total_requests = 0


# Global singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get or create global EmbeddingService instance.

    Returns:
        EmbeddingService singleton
    """
    global _embedding_service

    if _embedding_service is None:
        dimensions = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        _embedding_service = EmbeddingService(dimensions=dimensions)

    return _embedding_service
