"""Workspace-scoped knowledge retrieval.

The workspace id is a required constructor argument and is applied again to every
SQL statement (both the chunk table and its parent document table). There is no
code path that can search across tenants.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingProvider, ProviderError
from app.config import settings
from app.models.knowledge import DocumentChunk, KnowledgeDocument

logger = logging.getLogger(__name__)


def cosine_similarity(left: List[float], right: List[float]) -> float:
    """Cosine similarity in [-1, 1]; returns 0 for incompatible or empty vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    score = dot / (math.sqrt(left_norm) * math.sqrt(right_norm))
    return max(-1.0, min(1.0, score))


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float


@dataclass
class RetrievalResult:
    chunks: List[RetrievedChunk] = field(default_factory=list)
    candidates_scanned: int = 0
    threshold: float = 0.0
    provider: str = "mock"

    @property
    def top_score(self) -> float:
        return self.chunks[0].score if self.chunks else 0.0


class KnowledgeRetriever:
    """Retrieves the most similar indexed chunks for one workspace."""

    def __init__(
        self,
        db: AsyncSession,
        workspace_id: str,
        embedding_provider: EmbeddingProvider,
        threshold: float,
        *,
        scan_limit: Optional[int] = None,
    ):
        if not workspace_id:
            raise ValueError("workspace_id is required for knowledge retrieval.")
        self.db = db
        self.workspace_id = workspace_id
        self.embedding_provider = embedding_provider
        self.threshold = threshold
        self.scan_limit = scan_limit or settings.RETRIEVAL_SCAN_LIMIT

    def _dialect_name(self) -> str:
        bind = self.db.get_bind()
        return bind.dialect.name if bind is not None else "sqlite"

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        threshold: Optional[float] = None,
        exclude_document_ids: Optional[List[str]] = None,
    ) -> RetrievalResult:
        cutoff = self.threshold if threshold is None else threshold
        query = (query or "").strip()
        if not query:
            return RetrievalResult(threshold=cutoff, provider=self.embedding_provider.name)

        try:
            query_vector = await self.embedding_provider.embed_query(query)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise ProviderError("The embedding provider failed while embedding the query.") from exc

        if not query_vector or not any(query_vector):
            return RetrievalResult(threshold=cutoff, provider=self.embedding_provider.name)

        filters = [
            DocumentChunk.workspace_id == self.workspace_id,
            KnowledgeDocument.workspace_id == self.workspace_id,
            KnowledgeDocument.status == "indexed",
            KnowledgeDocument.embedding_dimension == len(query_vector),
            DocumentChunk.embedding.isnot(None),
        ]
        if exclude_document_ids:
            filters.append(KnowledgeDocument.id.notin_(exclude_document_ids))

        base = (
            select(DocumentChunk, KnowledgeDocument.title)
            .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
            .where(*filters)
        )

        if self._dialect_name() == "postgresql":
            distance = DocumentChunk.embedding.op("<=>")(query_vector)
            stmt = base.add_columns(distance.label("cosine_distance")).order_by(distance).limit(self.scan_limit)
            rows = (await self.db.execute(stmt)).all()
            scored = [
                (chunk, title, 1.0 - float(distance_value))
                for chunk, title, distance_value in rows
            ]
        else:
            # SQLite fallback: embeddings are stored as JSON, so score in Python.
            stmt = base.order_by(KnowledgeDocument.created_at.desc()).limit(self.scan_limit)
            rows = (await self.db.execute(stmt)).all()
            scored = [
                (chunk, title, cosine_similarity(query_vector, chunk.embedding or []))
                for chunk, title in rows
            ]

        hits = [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_title=title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=round(score, 6),
            )
            for chunk, title, score in scored
            if score >= cutoff
        ]
        hits.sort(key=lambda hit: (-hit.score, hit.document_title, hit.chunk_index))

        return RetrievalResult(
            chunks=hits[: max(1, top_k)],
            candidates_scanned=len(scored),
            threshold=cutoff,
            provider=self.embedding_provider.name,
        )
