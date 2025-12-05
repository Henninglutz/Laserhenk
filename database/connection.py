"""
PostgreSQL Connection für LASERHENK

Unterstützt 384-dimensionale Embeddings (z.B. sentence-transformers).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
import logging

logger = logging.getLogger(__name__)


class Database:
    """
    Singleton Database Connection.

    Konfiguration über Environment Variables:
    - DATABASE_URL oder POSTGRES_CONNECTION_STRING: PostgreSQL Connection String
    - EMBEDDING_DIMENSION: Vector-Dimension (default: 384)

    Usage:
        db = Database()
        async with db.session() as session:
            result = await session.execute(text("SELECT * FROM fabrics LIMIT 5"))
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Support both DATABASE_URL and POSTGRES_CONNECTION_STRING
        self.database_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_CONNECTION_STRING")
        if not self.database_url:
            raise ValueError("DATABASE_URL or POSTGRES_CONNECTION_STRING not set in environment")

        # Convert postgresql:// to postgresql+asyncpg:// for async support
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Embedding Dimension (384 für sentence-transformers/all-MiniLM-L6-v2)
        self.embedding_dim = int(os.getenv("EMBEDDING_DIMENSION", "384"))

        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20
        )

        self.AsyncSessionLocal = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        self._initialized = True
        logger.info(
            f"[Database] Connected: {self._mask_url(self.database_url)} "
            f"| Embedding dimension: {self.embedding_dim}"
        )

    def session(self) -> AsyncSession:
        """Returns new async session"""
        return self.AsyncSessionLocal()

    async def close(self):
        """Close all connections"""
        await self.engine.dispose()
        logger.info("[Database] Connections closed")

    def _mask_url(self, url: str) -> str:
        """Mask password in URL for logging"""
        if "@" in url:
            parts = url.split("@")
            return f"***@{parts[1]}"
        return url
