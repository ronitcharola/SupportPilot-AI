"""Resolves per-workspace AI configuration into provider instances."""
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingProvider, LLMProvider
from app.ai.factory import get_embedding_provider, get_llm_provider, resolve_similarity_threshold
from app.config import settings
from app.models.workspace import WorkspaceSettings


async def load_workspace_settings(db: AsyncSession, workspace_id: str) -> Optional[WorkspaceSettings]:
    result = await db.execute(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def embedding_provider_for_workspace(
    db: AsyncSession, workspace_id: str
) -> Tuple[EmbeddingProvider, Optional[WorkspaceSettings]]:
    ws_settings = await load_workspace_settings(db, workspace_id)
    provider_name = (ws_settings.embedding_provider if ws_settings else None) or settings.EMBEDDING_PROVIDER
    # The pgvector column has a fixed dimension; every provider must match it.
    provider = get_embedding_provider(provider_name, settings.EMBEDDING_DIMENSION)
    return provider, ws_settings


async def llm_provider_for_workspace(
    db: AsyncSession, workspace_id: str
) -> Tuple[LLMProvider, Optional[WorkspaceSettings]]:
    ws_settings = await load_workspace_settings(db, workspace_id)
    provider_name = (ws_settings.llm_provider if ws_settings else None) or settings.LLM_PROVIDER
    model = ws_settings.llm_model if ws_settings else None
    return get_llm_provider(provider_name, model), ws_settings


def similarity_threshold(provider_name: str, ws_settings: Optional[WorkspaceSettings]) -> float:
    configured = ws_settings.similarity_threshold if ws_settings else None
    return resolve_similarity_threshold(provider_name, configured)
