import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development", description="Environment: development, test, production")
    DEMO_MODE: bool = Field(default=True, description="Enable mock providers, seeded data, and mock services")
    
    # Auth & Security
    SECRET_KEY: str = Field(default="dev-super-secret-key-change-in-production-min-32-chars-supportpilot", description="JWT secret key")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)  # 24 hours
    CSRF_COOKIE_NAME: str = Field(default="csrf_token")
    AUTH_COOKIE_NAME: str = Field(default="access_token")
    
    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./supportpilot.db")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # AI Providers
    LLM_PROVIDER: str = Field(default="mock")  # mock | openai | gemini
    LLM_MODEL: str = Field(default="mock-gpt-4o")
    EMBEDDING_PROVIDER: str = Field(default="mock")  # mock | openai | gemini
    EMBEDDING_DIMENSION: int = Field(default=1536)
    SIMILARITY_THRESHOLD: float = Field(default=0.72)
    # Mock embeddings are lexical sketches; they use a separately calibrated cutoff.
    MOCK_SIMILARITY_THRESHOLD: float = Field(default=0.12)
    OPENAI_EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    GEMINI_EMBEDDING_MODEL: str = Field(default="text-embedding-004")
    GEMINI_LLM_MODEL: str = Field(default="gemini-1.5-flash")

    # AI triage (Phase 4)
    AI_LOW_CONFIDENCE_THRESHOLD: float = Field(default=0.55)

    # Human-in-the-loop approvals (Phase 5)
    # Support agents may approve refunds up to this amount; above it an Admin must decide.
    AGENT_APPROVAL_LIMIT_USD: float = Field(default=250.0)
    # Same idea for percentage discounts.
    AGENT_DISCOUNT_LIMIT_PERCENT: float = Field(default=25.0)
    PROPOSAL_DEFAULT_EXPIRY_HOURS: int = Field(default=24)

    # Knowledge base / RAG
    KNOWLEDGE_INGESTION_MODE: str = Field(default="inline")  # inline | celery
    MAX_UPLOAD_BYTES: int = Field(default=5 * 1024 * 1024)
    KNOWLEDGE_CHUNK_SIZE: int = Field(default=900)
    KNOWLEDGE_CHUNK_OVERLAP: int = Field(default=150)
    RETRIEVAL_SCAN_LIMIT: int = Field(default=2000)
    
    OPENAI_API_KEY: str = Field(default="")
    GEMINI_API_KEY: str = Field(default="")
    
    # Storage
    STORAGE_BACKEND: str = Field(default="local")
    STORAGE_LOCAL_PATH: str = Field(default="./uploads")
    
    # CORS
    FRONTEND_URL: str = Field(default="http://localhost:3000")
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
