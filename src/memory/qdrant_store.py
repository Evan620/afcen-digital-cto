"""Qdrant-based semantic memory for the Digital CTO.

Stores vector embeddings for codebase context, enabling the Code Review agent
to understand the full project architecture, not just the diff.
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.config import settings

logger = logging.getLogger(__name__)

# Default embedding dimension (OpenAI text-embedding-3-small = 1536)
DEFAULT_EMBEDDING_DIM = 1536
COLLECTION_NAME = "codebase_knowledge"


class QdrantStore:
    """Async Qdrant client for semantic memory (codebase embeddings)."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or settings.qdrant_url
        self._client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        """Connect to Qdrant and ensure the collection exists."""
        self._client = AsyncQdrantClient(url=self._url)

        # Create collection if it doesn't exist
        collections = await self._client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if COLLECTION_NAME not in collection_names:
            await self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=DEFAULT_EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection '%s'", COLLECTION_NAME)
        else:
            logger.info("Qdrant collection '%s' already exists", COLLECTION_NAME)

    async def disconnect(self) -> None:
        """Close the Qdrant client."""
        if self._client:
            await self._client.close()
            logger.info("Qdrant connection closed")

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise RuntimeError("Qdrant not connected. Call connect() first.")
        return self._client

    # ── Store & Retrieve ──

    async def store_embedding(
        self,
        point_id: str,
        vector: list[float],
        metadata: dict[str, Any],
    ) -> None:
        """Store a single embedding with metadata.

        Args:
            point_id: Unique identifier (e.g. 'repo:file:sha')
            vector: Embedding vector (1536-dim for OpenAI)
            metadata: Keys like 'file_path', 'repo', 'content_preview', 'sha'
        """
        await self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=metadata,
                )
            ],
        )

    async def search_similar(
        self,
        query_vector: list[float],
        limit: int = 5,
        filter_conditions: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Find the most similar code chunks to a query vector.

        Returns a list of dicts with 'id', 'score', and 'payload' keys.
        """
        results = await self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results.points
        ]

    # ── Health ──

    async def health_check(self) -> bool:
        """Return True if Qdrant is reachable."""
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False
