from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

KNOWLEDGE_STATUS_PATTERN = "^(pending|processing|indexed|failed)$"


class KnowledgeTextCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    content: str = Field(min_length=20, max_length=200_000)


class KnowledgeDocumentResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    filename: Optional[str] = None
    source_type: str
    content_type: Optional[str] = None
    size_bytes: int
    char_count: int
    chunk_count: int
    status: str
    error_message: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    uploaded_by_user_id: Optional[str] = None
    uploaded_by_name: Optional[str] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeChunkResponse(BaseModel):
    id: str
    chunk_index: int
    content: str
    char_count: int


class KnowledgeDocumentDetailResponse(KnowledgeDocumentResponse):
    chunks: List[KnowledgeChunkResponse] = []


class KnowledgeDocumentListResponse(BaseModel):
    items: List[KnowledgeDocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class KnowledgeSearchHitResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    excerpt: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[KnowledgeSearchHitResponse]
    candidates_scanned: int
    threshold: float
    provider: str
    took_ms: int


class KnowledgeStatsResponse(BaseModel):
    total_documents: int
    indexed_documents: int
    processing_documents: int
    failed_documents: int
    total_chunks: int
    total_characters: int
    embedding_provider: str
    embedding_dimension: int
    similarity_threshold: float
    retrieval_scan_limit: int
