"""Grounded knowledge-base chat with citations and low-evidence escalation.

The AI may only answer from retrieved, workspace-scoped knowledge. When nothing
clears the similarity threshold, or the provider returns no usable answer, the
response is explicitly escalated to a human instead of guessing.
"""
import logging
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderError
from app.ai.prompt_defense import (
    GROUNDED_SYSTEM_PROMPT,
    build_grounded_prompt,
    extract_cited_numbers,
    redact_unsafe_answer,
    sanitize_untrusted_text,
)
from app.ai.retriever import KnowledgeRetriever
from app.models.workspace import Workspace
from app.schemas.ai import ChatCitation, ChatResponse
from app.services.ai_config import (
    embedding_provider_for_workspace,
    llm_provider_for_workspace,
    similarity_threshold,
)

logger = logging.getLogger(__name__)

_NO_EVIDENCE_MESSAGE = (
    "I couldn't find an answer to that in the {workspace} knowledge base. "
    "This question needs a human support agent — please submit a support request and the team will follow up."
)


def _escalation(
    workspace_name: str,
    *,
    reason: str,
    provider: str,
    model: str,
    threshold: float,
    candidates_scanned: int,
    top_score: float = 0.0,
) -> ChatResponse:
    return ChatResponse(
        answer=_NO_EVIDENCE_MESSAGE.format(workspace=workspace_name),
        grounded=False,
        escalated=True,
        escalation_reason=reason,
        citations=[],
        provider=provider,
        model=model,
        threshold=threshold,
        top_score=round(top_score, 4),
        candidates_scanned=candidates_scanned,
    )


async def answer_customer_question(
    db: AsyncSession,
    *,
    message: str,
    workspace_slug: str,
    customer_email: Optional[str] = None,
    top_k: int = 4,
) -> ChatResponse:
    result = await db.execute(
        select(Workspace).where(Workspace.slug == workspace_slug, Workspace.is_active == True)  # noqa: E712
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_slug}' not found.",
        )

    embedding_provider, ws_settings = await embedding_provider_for_workspace(db, workspace.id)
    threshold = similarity_threshold(embedding_provider.name, ws_settings)
    retriever = KnowledgeRetriever(db, workspace.id, embedding_provider, threshold)

    try:
        retrieval = await retriever.retrieve(message, top_k=top_k)
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The AI provider is unavailable: {exc}",
        ) from exc

    llm, _ = await llm_provider_for_workspace(db, workspace.id)

    if not retrieval.chunks:
        logger.info(
            "Chat escalated: no evidence in workspace %s (scanned=%s, threshold=%s)",
            workspace.id,
            retrieval.candidates_scanned,
            threshold,
        )
        return _escalation(
            workspace.name,
            reason="No knowledge-base content matched this question above the similarity threshold.",
            provider=llm.name,
            model=llm.model,
            threshold=threshold,
            candidates_scanned=retrieval.candidates_scanned,
        )

    prompt = build_grounded_prompt(
        message,
        [
            (hit.document_title, hit.chunk_index, hit.content)
            for hit in retrieval.chunks
        ],
    )

    try:
        completion = await llm.complete(
            GROUNDED_SYSTEM_PROMPT,
            prompt,
            max_tokens=500,
            temperature=0.2,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The AI provider is unavailable: {exc}",
        ) from exc

    answer = redact_unsafe_answer(completion.content)
    if not answer:
        return _escalation(
            workspace.name,
            reason="The AI could not produce a grounded answer from the retrieved context.",
            provider=completion.provider,
            model=completion.model,
            threshold=threshold,
            candidates_scanned=retrieval.candidates_scanned,
            top_score=retrieval.top_score,
        )

    numbered = list(enumerate(retrieval.chunks, start=1))
    cited = extract_cited_numbers(answer)
    if cited:
        numbered = [(number, hit) for number, hit in numbered if number in cited]

    citations: List[ChatCitation] = [
        ChatCitation(
            number=number,
            document_id=hit.document_id,
            document_title=hit.document_title,
            chunk_index=hit.chunk_index,
            excerpt=sanitize_untrusted_text(hit.content, max_length=400),
            score=hit.score,
        )
        for number, hit in numbered
    ]

    return ChatResponse(
        answer=answer,
        grounded=True,
        escalated=False,
        citations=citations,
        provider=completion.provider,
        model=completion.model,
        threshold=threshold,
        top_score=retrieval.top_score,
        candidates_scanned=retrieval.candidates_scanned,
    )
