from typing import List, Optional

from pydantic import BaseModel

from app.schemas.ai import ChatCitation


class SuggestedReplyResponse(BaseModel):
    ticket_id: str
    draft: Optional[str] = None
    grounded: bool
    citations: List[ChatCitation] = []
    provider: str
    model: str
    threshold: float
    top_score: float
    candidates_scanned: int
    note: Optional[str] = None
