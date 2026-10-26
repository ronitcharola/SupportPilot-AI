from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ai import ChatRequest, ChatResponse
from app.services.chat_service import answer_customer_question

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/chat", response_model=ChatResponse)
async def grounded_chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Answers a customer question strictly from the workspace knowledge base.

    Returns citations for grounded answers. When retrieval finds no evidence, the
    response is marked `escalated` and no answer is invented. This endpoint is
    read-only: it cannot create tickets or execute consequential actions.
    """
    return await answer_customer_question(
        db,
        message=data.message,
        workspace_slug=data.workspace_slug,
        customer_email=data.customer_email,
        top_k=data.top_k,
    )
