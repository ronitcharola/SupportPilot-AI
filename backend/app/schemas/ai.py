from typing import List, Optional

from pydantic import BaseModel, Field

WORKSPACE_SLUG_PATTERN = "^[a-z0-9][a-z0-9-]{0,99}$"


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)
    workspace_slug: str = Field(default="acme-corp", pattern=WORKSPACE_SLUG_PATTERN)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    top_k: int = Field(default=4, ge=1, le=10)


class ChatCitation(BaseModel):
    number: int
    document_id: str
    document_title: str
    chunk_index: int
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    escalated: bool
    escalation_reason: Optional[str] = None
    citations: List[ChatCitation] = []
    provider: str
    model: str
    threshold: float
    top_score: float
    candidates_scanned: int
